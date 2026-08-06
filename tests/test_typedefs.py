from __future__ import annotations

from typing import TYPE_CHECKING

import sympy

from kconfig.core.cache import build_typedef_location_cache
from kconfig.core.parser import get_custom_members, get_typedef_configs, resolve_typedef
from kconfig.core.query.query import parse_source
from kconfig.types import KconfigFieldType
from tests.conftest import find_node

if TYPE_CHECKING:
    from pathlib import Path

CONFIG_64BIT = sympy.Symbol("CONFIG_64BIT")


def _write_elf_header(kernel_dir: Path) -> None:
    (kernel_dir / "elf.h").write_bytes(
        b"#ifdef CONFIG_64BIT\n#define Elf_Sym Elf64_Sym\n#else\n#define Elf_Sym Elf32_Sym\n#endif\n"
    )


def test_resolve_typedef_finds_both_expansions(kernel_dir: Path) -> None:
    _write_elf_header(kernel_dir)
    build_typedef_location_cache()

    candidates = resolve_typedef("Elf_Sym")
    by_type = {c.resolved_type: c.guard for c in candidates}
    assert by_type == {
        "Elf64_Sym": CONFIG_64BIT,
        "Elf32_Sym": sympy.Not(CONFIG_64BIT),
    }


def test_get_typedef_configs_matching_type(kernel_dir: Path) -> None:
    _write_elf_header(kernel_dir)
    build_typedef_location_cache()

    guard = get_typedef_configs(KconfigFieldType("Elf_Sym"), "Elf64_Sym")
    assert guard == CONFIG_64BIT


def test_get_typedef_configs_impossible_type(kernel_dir: Path) -> None:
    _write_elf_header(kernel_dir)
    build_typedef_location_cache()

    guard = get_typedef_configs(KconfigFieldType("Elf_Sym"), "totally_unrelated")
    assert guard == sympy.false


def test_get_typedef_configs_no_candidates_is_unconditional(kernel_dir: Path) -> None:  # noqa: ARG001
    build_typedef_location_cache()

    guard = get_typedef_configs(KconfigFieldType("Never_Defined_Anywhere"), "whatever")
    assert guard == sympy.true


def test_get_typedef_configs_direct_match_needs_no_lookup(kernel_dir: Path) -> None:  # noqa: ARG001
    build_typedef_location_cache()

    guard = get_typedef_configs(KconfigFieldType("int"), "int")
    assert guard == sympy.true


def test_get_custom_members_distinguishes_tags_from_typedefs() -> None:
    source = b"static int f(struct foo *f, union bar *b, mytype_t x) { struct baz z; return 0; }"
    root = parse_source(source)
    func_def = find_node(root, "function_definition")

    members = get_custom_members(func_def)
    assert members.structs == {"foo", "baz"}
    assert members.unions == {"bar"}
    assert members.typedefs == {"mytype_t"}
