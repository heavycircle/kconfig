from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.cache import (
    build_module_location_cache,
    build_struct_location_cache,
    get_module_location,
    get_struct_location,
)
from kconfig.core.cache.typedefs import cache_typedef_locations, get_typedef_locations
from kconfig.core.config import kconfig_state
from kconfig.core.parser import dispatch
from kconfig.core.query import run_alias_list
from kconfig.core.structs.module import find_struct_declaration
from kconfig.types import KconfigParserState

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_MACRO_NOISE = b"""
#define sockaddr_storage __kernel_sockaddr_storage
#define MAX_SIZE 128
#define SOME_FLAG (1 << 3)
typedef struct foo bar_t;
"""


def test_run_alias_list_ignores_non_identifier_macro_values(tmp_path: Path) -> None:
    header = tmp_path / "alias.h"
    header.write_bytes(_MACRO_NOISE)

    aliases = run_alias_list(header)
    assert set(aliases) == {"sockaddr_storage", "bar_t"}


def test_typedef_cache_ignores_non_identifier_macro_values(kernel_dir: Path) -> None:
    (kernel_dir / "alias.h").write_bytes(_MACRO_NOISE)
    cache_typedef_locations()

    assert get_typedef_locations("sockaddr_storage")
    assert get_typedef_locations("bar_t")
    assert get_typedef_locations("MAX_SIZE") == []
    assert get_typedef_locations("SOME_FLAG") == []


def test_rank_file_prefers_real_include_over_tools_mirror(kernel_dir: Path) -> None:
    # A struct defined in both the real kernel headers and a tools/ mirror header
    # (a real pattern in the Linux tree, e.g. list_head) must resolve to the real one.
    (kernel_dir / "include").mkdir()
    (kernel_dir / "include" / "types.h").write_text("struct foo { int real; };\n")

    (kernel_dir / "tools" / "include").mkdir(parents=True)
    (kernel_dir / "tools" / "include" / "types.h").write_text("struct foo { int mirrored; };\n")

    build_struct_location_cache()
    location = get_struct_location("foo")
    assert location is not None
    assert location.file_path == kernel_dir / "include" / "types.h"


def test_rank_file_prefers_the_target_architecture(kernel_dir: Path) -> None:
    # Regression: every arch/*/include/asm/ header can define the same struct
    # name (e.g. thread_info) at its own, unrelated line number. Ranking by
    # line number as a tiebreaker (with no architecture awareness at all) let
    # a completely wrong architecture win just because its definition happened
    # to start earlier in its own file -- confirmed against a real vmlinux,
    # where arch/parisc's thread_info (line 9) beat arch/x86's (line 56) for
    # an x86_64 target, comparing the wrong struct shape entirely.
    (kernel_dir / "arch" / "parisc" / "include" / "asm").mkdir(parents=True)
    (kernel_dir / "arch" / "parisc" / "include" / "asm" / "thread_info.h").write_text(
        "struct thread_info { int preempt_count; };\n"
    )

    (kernel_dir / "arch" / "x86" / "include" / "asm").mkdir(parents=True)
    x86_header = (kernel_dir / "arch" / "x86" / "include" / "asm" / "thread_info.h").open("w")
    x86_header.write("\n" * 10)  # push the real definition to a later line than parisc's
    x86_header.write("struct thread_info { unsigned long flags; unsigned int cpu; };\n")
    x86_header.close()

    kconfig_state.arch = "x86"
    build_struct_location_cache()
    location = get_struct_location("thread_info")
    assert location is not None
    assert location.file_path == kernel_dir / "arch" / "x86" / "include" / "asm" / "thread_info.h"

    # A different target architecture must resolve to its own definition instead.
    kconfig_state.arch = "parisc"
    build_struct_location_cache()
    location = get_struct_location("thread_info")
    assert location is not None
    assert location.file_path == kernel_dir / "arch" / "parisc" / "include" / "asm" / "thread_info.h"


def test_module_struct_lookup_reads_pahole_text_not_the_binary(
    kernel_dir: Path,  # noqa: ARG001 -- needed so kconfig_state.kernel_dir is set
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # cache_module_structs shells out to `pahole` against a real binary; stub that
    # out and confirm struct lookups parse the pahole *text* dump it produces, not
    # the (fake, unparseable) binary path itself.
    module_dir = tmp_path / "modules"
    module_dir.mkdir()
    (module_dir / "vmlinux").write_bytes(b"\x00\x01not-real-elf-data")
    kconfig_state.module_dir = module_dir

    pahole_output = b"/* <1> fake.c:1 */\nstruct foo {\n\tint x;                /*     0     4 */\n};\n"

    class FakeResult:
        returncode = 0
        stdout = pahole_output
        stderr = b""

    monkeypatch.setattr("kconfig.core.cache.modules.subprocess.run", lambda *_a, **_k: FakeResult())

    build_module_location_cache()
    assert get_module_location("foo") is not None

    node, struct = find_struct_declaration("foo")
    assert struct.original_name == "foo"

    state = KconfigParserState()
    dispatch.dispatch(node, state)
    assert [f.field_name for f in state.fields] == ["x"]
