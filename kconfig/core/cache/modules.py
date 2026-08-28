from __future__ import annotations

import hashlib
import itertools
import pickle
import subprocess
from typing import TYPE_CHECKING

from kconfig.core.config import CACHE_MODULE_DIR, kconfig_state
from kconfig.core.query import run_struct_list
from kconfig.exceptions import KconfigSubprocessFailedError
from kconfig.types import KconfigModuleCapabilities
from kconfig.ui import ui

if TYPE_CHECKING:
    from pathlib import Path

MODULE_CACHE: dict[str, Path] = {}
"""Cache containing module definition locations."""


def get_pahole_file(file: Path) -> Path:
    """Get the stored pahole file for a given kernel module."""
    file_hash = hashlib.sha256(str(file).replace("/", "_").encode()).hexdigest()
    return CACHE_MODULE_DIR / f"{file.stem}_{file_hash}.h"


def _run(cmd: list[str], tool: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(cmd, check=False, capture_output=True)  # noqa: S603
    except FileNotFoundError as e:
        raise KconfigSubprocessFailedError(tool, f"'{tool}' not found on PATH") from e


def _section_names(file: Path) -> set[str]:
    """ELF section names present in ``file``, via ``readelf -SW`` (wide, one row per section).

    A non-zero exit (e.g. ``file`` isn't a valid ELF object) is treated as
    "nothing known" rather than raised -- a single malformed input shouldn't
    abort probing every other module.
    """
    result = _run(["readelf", "-SW", str(file)], "readelf")
    if result.returncode != 0:
        return set()

    names = set()
    for line in result.stdout.decode(errors="replace").splitlines():
        if "]" not in line:
            continue
        after_bracket = line.split("]", 1)[1].strip()
        if after_bracket.startswith("."):
            names.add(after_bracket.split()[0])
    return names


def _modinfo_strings(file: Path) -> dict[str, str]:
    """Parse the ``.modinfo`` section's ``key=value`` strings via ``readelf -p``.

    Avoids depending on the ``modinfo`` kmod tool (not always installed
    alongside the standard binutils/pahole toolchain this project already
    requires).
    """
    result = _run(["readelf", "-p", ".modinfo", str(file)], "readelf")
    if result.returncode != 0:
        return {}

    info: dict[str, str] = {}
    for raw_line in result.stdout.decode(errors="replace").splitlines():
        line = raw_line.strip()
        if not line.startswith("["):
            continue
        _, _, value = line.partition("]")
        value = value.strip()
        if not value:
            continue
        key, sep, val = value.partition("=")
        info[key] = val if sep else ""
    return info


def _try_pahole(file: Path, vmlinux: Path | None) -> tuple[bytes | None, bool]:
    """Attempt to extract struct layout via pahole, retrying with a BTF base if needed.

    A module built with ``CONFIG_DEBUG_INFO_BTF_MODULES`` only carries a
    distilled BTF delta against the vmlinux it was built alongside -- pahole
    needs ``--btf_base <vmlinux>`` to resolve it. A plain ``pahole -I`` on
    such a module fails even though real struct layout is recoverable, so
    that's retried here before giving up.

    Returns:
        tuple[bytes | None, bool]: The raw pahole output (``None`` if no
            struct layout could be extracted at all), and whether a BTF base
            was required to get it.

    """
    result = _run(["pahole", "-I", str(file)], "pahole")
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout, False

    if vmlinux is not None and vmlinux != file:
        result = _run(["pahole", "--btf_base", str(vmlinux), "-I", str(file)], "pahole")
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout, True

    return None, False


def probe_module(file: Path, vmlinux: Path | None) -> tuple[KconfigModuleCapabilities, bytes | None]:
    """Probe one module/vmlinux file's introspection capabilities.

    Returns the capabilities alongside the raw pahole struct dump when struct
    layout was actually extractable, so callers building the real struct
    cache don't need to invoke pahole a second time for the same file.
    """
    sections = _section_names(file)
    modinfo = _modinfo_strings(file)
    pahole_output, needs_btf_base = _try_pahole(file, vmlinux)

    capabilities = KconfigModuleCapabilities(
        file=file,
        has_dwarf=".debug_info" in sections,
        has_btf=".BTF" in sections,
        struct_layout_available=pahole_output is not None,
        needs_btf_base=needs_btf_base,
        symtab_stripped=".symtab" not in sections,
        vermagic=modinfo.get("vermagic"),
        modinfo=modinfo,
    )
    return capabilities, pahole_output


def _iter_module_files(module_dir: Path) -> list[Path]:
    ko_files = module_dir.rglob("*.ko")
    vmlinux_files = list(module_dir.rglob("vmlinux"))
    return list(itertools.chain(ko_files, vmlinux_files))


def probe_all_modules(module_dir: Path) -> list[KconfigModuleCapabilities]:
    """Probe every module/vmlinux file in ``module_dir`` without touching the struct cache.

    Backs ``kconfig module info`` -- a fast, read-only diagnostic for seeing
    which files will get full struct-layout comparison in ``struct
    analyze``/``signature analyze`` versus a degraded fallback tier, before
    running either.
    """
    target_files = _iter_module_files(module_dir)
    vmlinux = next((f for f in target_files if f.name == "vmlinux"), None)
    return [probe_module(file, vmlinux)[0] for file in target_files]


def cache_module_structs() -> None:
    """Build the module struct cache for compiled kernel modules via ``pahole``.

    A module without usable BTF/DWARF struct layout (common for
    production/stripped builds) is skipped with a warning rather than
    aborting the whole batch -- one such file used to take down caching for
    every other module in the directory. Its coarser, module-level facts
    (vermagic, ...) are still available via ``kconfig module info``, even
    though they aren't yet folded into struct-layout evidence.
    """
    ui.out_info("Warming the module capability cache (this may take a minute) ...")
    MODULE_CACHE.clear()

    target_files = _iter_module_files(kconfig_state.module_dir)
    if not target_files:
        ui.out_warning(f"No .ko files found in {kconfig_state.module_dir}")
        return

    vmlinux = next((f for f in target_files if f.name == "vmlinux"), None)
    degraded = 0

    for file in target_files:
        capabilities, pahole_output = probe_module(file, vmlinux)
        if pahole_output is None:
            degraded += 1
            ui.out_warning(
                f"No usable struct layout for {file.name} ({capabilities.tier}); "
                "skipping -- run `kconfig module info` for details."
            )
            continue

        # Save the pahole output
        pahole_file = get_pahole_file(file)
        with pahole_file.open("wb") as f:
            f.write(pahole_output)

        # Store the pahole dump, not the binary -- that's what struct lookups
        # actually parse back later (see core/structs/module.py).
        for _, struct in run_struct_list(code=pahole_output):
            MODULE_CACHE[struct.original_name] = pahole_file

    module_cache_file = CACHE_MODULE_DIR / f"cache_module_{kconfig_state.kernel_dir.name.replace('.', '_')}.pkl"
    with module_cache_file.open("wb") as f:
        pickle.dump(MODULE_CACHE, f, protocol=pickle.HIGHEST_PROTOCOL)

    usable = len(target_files) - degraded
    if degraded:
        ui.out_warning(f"{degraded}/{len(target_files)} module file(s) had no usable struct layout.")
    ui.out_success(f"Cached capabilities for {usable}/{len(target_files)} module file(s)!")


def build_module_location_cache() -> None:
    """Load the module cache from disk, or build it if it's missing/invalid."""
    module_cache_file = CACHE_MODULE_DIR / f"cache_module_{kconfig_state.kernel_dir.name.replace('.', '_')}.pkl"
    if not module_cache_file.exists():
        cache_module_structs()
        return

    try:
        with module_cache_file.open("rb") as f:
            MODULE_CACHE.clear()
            MODULE_CACHE.update(pickle.load(f))  # noqa: S301

        ui.out_debug(f"Loaded {len(MODULE_CACHE)} modules from disk cache.")
    except (pickle.UnpicklingError, KeyError, TypeError):
        ui.out_warning("Cache file corrupted. Rebuilding ...")
        cache_module_structs()


def get_module_location(struct_name: str) -> Path | None:
    """Get the location of a struct definition in our modules."""
    return MODULE_CACHE.get(struct_name)
