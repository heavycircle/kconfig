from __future__ import annotations

from typing import TYPE_CHECKING

import sympy

from kconfig.core.cache import build_struct_location_cache
from kconfig.core.parser import dispatch
from kconfig.core.structs import find_struct_declaration
from kconfig.types import KconfigParserState
from tests.conftest import parse_and_dispatch

if TYPE_CHECKING:
    from pathlib import Path

CONFIG_64BIT = sympy.Symbol("CONFIG_64BIT")


def test_flat_struct_fields() -> None:
    state = parse_and_dispatch(b"struct foo { int x; char *name; };")
    fields = {f.field_name: f.field_type.original_type for f in state.fields}
    assert fields == {"x": "int", "name": "char *"}


def test_array_field() -> None:
    state = parse_and_dispatch(b"struct foo { int arr[8]; };")
    field = state.fields[0]
    assert field.field_name == "arr"
    assert field.field_type.original_type == "int [8]"


def test_ifdef_and_ifndef_produce_opposite_guards() -> None:
    source = b"""
    struct foo {
    #ifdef CONFIG_64BIT
        long sixty_four;
    #endif
    #ifndef CONFIG_64BIT
        int thirty_two;
    #endif
    };
    """
    state = parse_and_dispatch(source)
    guards = {f.field_name: f.guard for f in state.fields}
    assert guards["sixty_four"] == CONFIG_64BIT
    assert guards["thirty_two"] == sympy.Not(CONFIG_64BIT)


def test_else_negates_the_guard() -> None:
    source = b"""
    struct foo {
    #ifdef CONFIG_64BIT
        long a;
    #else
        int a;
    #endif
    };
    """
    state = parse_and_dispatch(source)
    guards = {(f.field_name, f.field_type.original_type): f.guard for f in state.fields}
    assert guards[("a", "long")] == CONFIG_64BIT
    assert guards[("a", "int")] == sympy.Not(CONFIG_64BIT)


def test_elif_chain() -> None:
    source = b"""
    struct foo {
    #if defined(CONFIG_A)
        int a;
    #elif defined(CONFIG_B)
        int b;
    #else
        int c;
    #endif
    };
    """
    state = parse_and_dispatch(source)
    guards = {f.field_name: f.guard for f in state.fields}
    a, b = sympy.Symbol("CONFIG_A"), sympy.Symbol("CONFIG_B")
    assert guards["a"] == a
    assert guards["b"] == sympy.simplify(sympy.And(sympy.Not(a), b))
    assert guards["c"] == sympy.simplify(sympy.And(sympy.Not(a), sympy.Not(b)))


def test_header_guard_is_not_treated_as_a_config() -> None:
    source = b"""#ifndef _LINUX_FOO_H
#define _LINUX_FOO_H

#ifdef CONFIG_64BIT
#define Elf_Sym Elf64_Sym
#endif

#endif
"""
    state = parse_and_dispatch(source)
    assert len(state.fields) == 1
    field = state.fields[0]
    assert field.field_name == "Elf_Sym"
    assert field.guard == CONFIG_64BIT


def test_nested_ifndef_that_is_not_a_header_guard_is_still_a_real_guard() -> None:
    source = b"""#ifndef _LINUX_FOO_H
#define _LINUX_FOO_H

#ifndef CONFIG_FALLBACK
#define SOME_DEFAULT 1
#endif

#endif
"""
    state = parse_and_dispatch(source)
    assert len(state.fields) == 1
    assert state.fields[0].guard == sympy.Not(sympy.Symbol("CONFIG_FALLBACK"))


def test_preproc_def_without_value_is_ignored() -> None:
    state = parse_and_dispatch(b"#define FLAG_ONLY\n")
    assert state.fields == []


def test_type_definition_records_the_typedef() -> None:
    state = parse_and_dispatch(b"typedef struct bar *bar_ptr;")
    assert len(state.fields) == 1
    field = state.fields[0]
    assert field.field_name == "bar_ptr"
    assert field.field_type.original_type == "struct bar *"


def test_recursive_struct_field_layout(kernel_dir: Path) -> None:
    source = b"struct inner { int x; };\nstruct outer { struct inner a; };\n"
    (kernel_dir / "foo.h").write_bytes(source)
    build_struct_location_cache()

    node, _ = find_struct_declaration("outer")
    state = KconfigParserState(recursive=True)
    dispatch.dispatch(node, state)

    outer_field = next(f for f in state.fields if f.field_name == "a")
    assert outer_field.field_type.layout is not None
    assert [f.field_name for f in outer_field.field_type.layout.fields] == ["x"]


def test_non_recursive_struct_field_has_no_layout() -> None:
    source = b"""
    struct inner { int x; };
    struct outer { struct inner a; };
    """
    state = parse_and_dispatch(source, recursive=False)
    outer_field = next(f for f in state.fields if f.field_name == "a")
    assert outer_field.field_type.layout is None
