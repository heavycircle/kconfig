from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.cache.modules import (
    MODULE_CACHE,
    cache_module_structs,
    get_module_location,
    probe_all_modules,
    probe_module,
)
from kconfig.core.config import kconfig_state

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class FakeResult:
    def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


FULL_SECTIONS = b"""
  [ 1] .text             PROGBITS        0
  [ 2] .debug_info       PROGBITS        0
  [ 3] .BTF              PROGBITS        0
  [ 4] .symtab           SYMTAB          0
"""

STRIPPED_SECTIONS = b"""
  [ 1] .text             PROGBITS        0
"""

VERMAGIC_MODINFO = b"""
String dump of section '.modinfo':
  [     0]  license=GPL
  [    10]  vermagic=6.8.0-generic SMP mod_unload
"""

PAHOLE_STRUCT = b"/* <1> fake.c:1 */\nstruct foo {\n\tint x;                /*     0     4 */\n};\n"


def make_fake_run(
    *,
    sections: bytes = STRIPPED_SECTIONS,
    modinfo: bytes = b"",
    pahole_plain: tuple[int, bytes] = (1, b""),
    pahole_base: tuple[int, bytes] = (1, b""),
) -> object:
    def fake_run(cmd: list[str], **_kwargs: object) -> FakeResult:
        if cmd[0] == "readelf" and "-SW" in cmd:
            return FakeResult(0, sections)
        if cmd[0] == "readelf" and ".modinfo" in cmd:
            return FakeResult(0, modinfo)
        if cmd[0] == "pahole" and "--btf_base" in cmd:
            code, out = pahole_base
            return FakeResult(code, out)
        if cmd[0] == "pahole":
            code, out = pahole_plain
            return FakeResult(code, out)
        raise AssertionError(f"unexpected command: {cmd}")

    return fake_run


def test_probe_module_reports_full_tier_when_plain_pahole_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = make_fake_run(sections=FULL_SECTIONS, modinfo=VERMAGIC_MODINFO, pahole_plain=(0, PAHOLE_STRUCT))
    monkeypatch.setattr("kconfig.core.cache.modules.subprocess.run", fake)

    capabilities, output = probe_module(tmp_path / "foo.ko", vmlinux=None)

    assert capabilities.tier == "full"
    assert capabilities.has_dwarf
    assert capabilities.has_btf
    assert not capabilities.symtab_stripped
    assert not capabilities.needs_btf_base
    assert capabilities.vermagic == "6.8.0-generic SMP mod_unload"
    assert output == PAHOLE_STRUCT


def test_probe_module_falls_back_to_btf_base_when_plain_pahole_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = make_fake_run(sections=FULL_SECTIONS, pahole_plain=(1, b""), pahole_base=(0, PAHOLE_STRUCT))
    monkeypatch.setattr("kconfig.core.cache.modules.subprocess.run", fake)

    capabilities, output = probe_module(tmp_path / "foo.ko", vmlinux=tmp_path / "vmlinux")

    assert capabilities.tier == "split-btf"
    assert capabilities.needs_btf_base
    assert output == PAHOLE_STRUCT


def test_probe_module_does_not_retry_btf_base_without_a_vmlinux(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = make_fake_run(sections=FULL_SECTIONS, pahole_plain=(1, b""), pahole_base=(0, PAHOLE_STRUCT))
    monkeypatch.setattr("kconfig.core.cache.modules.subprocess.run", fake)

    capabilities, output = probe_module(tmp_path / "foo.ko", vmlinux=None)

    assert capabilities.tier == "none"
    assert output is None


def test_probe_module_reports_vermagic_only_when_pahole_fails_entirely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = make_fake_run(sections=STRIPPED_SECTIONS, modinfo=VERMAGIC_MODINFO)
    monkeypatch.setattr("kconfig.core.cache.modules.subprocess.run", fake)

    capabilities, output = probe_module(tmp_path / "foo.ko", vmlinux=tmp_path / "vmlinux")

    assert capabilities.tier == "vermagic-only"
    assert capabilities.symtab_stripped
    assert output is None


def test_probe_module_reports_none_tier_with_no_signal_at_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_fake_run()
    monkeypatch.setattr("kconfig.core.cache.modules.subprocess.run", fake)

    capabilities, output = probe_module(tmp_path / "foo.ko", vmlinux=None)

    assert capabilities.tier == "none"
    assert capabilities.vermagic is None
    assert output is None


def test_probe_all_modules_probes_every_ko_and_vmlinux_without_touching_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_dir = tmp_path / "modules"
    module_dir.mkdir()
    (module_dir / "a.ko").write_bytes(b"fake")
    (module_dir / "b.ko").write_bytes(b"fake")
    (module_dir / "vmlinux").write_bytes(b"fake")

    fake = make_fake_run(sections=FULL_SECTIONS, pahole_plain=(0, PAHOLE_STRUCT))
    monkeypatch.setattr("kconfig.core.cache.modules.subprocess.run", fake)

    capabilities = probe_all_modules(module_dir)

    assert {c.file.name for c in capabilities} == {"a.ko", "b.ko", "vmlinux"}
    assert all(c.tier == "full" for c in capabilities)
    assert MODULE_CACHE == {}


def test_cache_module_structs_skips_a_degraded_module_instead_of_aborting(
    kernel_dir: Path,  # noqa: ARG001 -- needed so kconfig_state.kernel_dir is set
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_dir = tmp_path / "modules"
    module_dir.mkdir()
    (module_dir / "good.ko").write_bytes(b"fake")
    (module_dir / "bad.ko").write_bytes(b"fake")
    kconfig_state.module_dir = module_dir

    def fake_run(cmd: list[str], **_kwargs: object) -> FakeResult:
        if cmd[0] == "readelf":
            return FakeResult(0, STRIPPED_SECTIONS if "-SW" in cmd else b"")
        if cmd[0] == "pahole":
            if cmd[-1].endswith("bad.ko"):
                return FakeResult(1, b"", b"no BTF found")
            return FakeResult(0, PAHOLE_STRUCT)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr("kconfig.core.cache.modules.subprocess.run", fake_run)

    cache_module_structs()

    assert get_module_location("foo") is not None
    assert len(MODULE_CACHE) == 1
