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


def test_named_nested_struct_does_not_inherit_the_referencing_guard(kernel_dir: Path) -> None:
    # Regression: a named nested struct has its own independent definition
    # (found via find_struct_declaration, possibly in a different file
    # entirely) -- its fields' guards must reflect only what's #ifdef'd
    # *within that definition*, not whatever guard was active at the site
    # that referenced it. Confirmed against a real vmlinux: tty_port_operations
    # (genuinely unconditional) had every field falsely guarded by CONFIG_SMP,
    # inherited from an unrelated #ifdef CONFIG_SMP many levels up the
    # reference chain that eventually reached it.
    source = b"""
    struct inner { int x; };

    struct outer {
    #ifdef CONFIG_SMP
        struct inner a;
    #endif
    };
    """
    (kernel_dir / "foo.h").write_bytes(source)
    build_struct_location_cache()

    node, _ = find_struct_declaration("outer")
    state = KconfigParserState(recursive=True)
    dispatch.dispatch(node, state)

    outer_field = next(f for f in state.fields if f.field_name == "a")
    assert outer_field.guard == sympy.Symbol("CONFIG_SMP")

    inner_field = outer_field.field_type.layout.fields[0]
    assert inner_field.guard is sympy.true


def test_non_recursive_struct_field_has_no_layout() -> None:
    source = b"""
    struct inner { int x; };
    struct outer { struct inner a; };
    """
    state = parse_and_dispatch(source, recursive=False)
    outer_field = next(f for f in state.fields if f.field_name == "a")
    assert outer_field.field_type.layout is None


def test_anonymous_struct_field_gets_an_inline_layout() -> None:
    source = b"struct outer { struct { int x; int y; } point; };"
    state = parse_and_dispatch(source, recursive=True)

    point = next(f for f in state.fields if f.field_name == "point")
    assert point.field_type.layout is not None
    assert point.field_type.layout.original_name == ""
    assert [f.field_name for f in point.field_type.layout.fields] == ["x", "y"]


def test_anonymous_union_field_gets_an_inline_layout() -> None:
    source = b"struct outer { union { int a; float b; } u; };"
    state = parse_and_dispatch(source, recursive=True)

    union_field = next(f for f in state.fields if f.field_name == "u")
    assert union_field.field_type.layout is not None
    assert [f.field_name for f in union_field.field_type.layout.fields] == ["a", "b"]


def test_truly_anonymous_member_still_gets_a_layout() -> None:
    # No declarator at all -- a C11 anonymous struct member.
    source = b"struct outer { struct { int z; }; };"
    state = parse_and_dispatch(source, recursive=True)

    assert len(state.fields) == 1
    field = state.fields[0]
    assert field.field_name.startswith("anonymous_")
    assert field.field_type.layout is not None
    assert [f.field_name for f in field.field_type.layout.fields] == ["z"]


def test_anonymous_struct_field_has_no_layout_when_not_recursive() -> None:
    source = b"struct outer { struct { int x; } point; };"
    state = parse_and_dispatch(source, recursive=False)

    point = next(f for f in state.fields if f.field_name == "point")
    assert point.field_type.layout is None


def test_multiple_declarators_sharing_one_type_are_all_recorded() -> None:
    # `struct list_head *next, *prev;` parses as ONE field_declaration with two
    # declarators -- a very common C idiom that used to silently drop everything
    # after the first declarator.
    state = parse_and_dispatch(b"struct foo { struct list_head *next, *prev; };")
    fields = {f.field_name: f.field_type.original_type for f in state.fields}
    assert fields == {"next": "struct list_head *", "prev": "struct list_head *"}


def test_anonymous_struct_with_multiple_declarators_is_resolved_once() -> None:
    # Regression: resolving an anonymous struct/union body per-declarator (instead
    # of once per field_declaration) re-dispatches the same body once per
    # declarator, which compounds multiplicatively with nesting depth. Three
    # levels of "2 declarators sharing an anonymous type" should be O(1) parses
    # per level (6 fields total), not 2*2*2 = 8 re-parses of the deepest level.
    source = b"""
    struct outer {
        struct {
            struct {
                struct { int x, y; } a, b;
            } c, d;
        } e, f;
    };
    """
    state = parse_and_dispatch(source, recursive=True)
    e, f = (next(fld for fld in state.fields if fld.field_name == n) for n in ("e", "f"))
    assert e.field_type.layout is f.field_type.layout

    c, d = e.field_type.layout.fields
    assert c.field_type.layout is d.field_type.layout

    a, b = c.field_type.layout.fields
    assert a.field_type.layout is b.field_type.layout
    assert [fld.field_name for fld in a.field_type.layout.fields] == ["x", "y"]


def test_trailing_attribute_macro_does_not_swallow_the_field_name() -> None:
    # Regression: tree-sitter's C grammar doesn't know about the kernel's
    # postfix attribute-like macros (____cacheline_aligned, __ro_after_init,
    # ...) -- `TYPE name MACRO;` isn't valid C to it, so it recovers by
    # wrapping the *real* name in an ERROR node and mistakenly treating the
    # trailing macro token as the declarator. Confirmed against a real
    # vmlinux: task_group's `atomic_long_t load_avg ____cacheline_aligned;`
    # was parsed as a field literally named "____cacheline_aligned", losing
    # "load_avg" entirely -- which then always reported as missing from the
    # module (it was never looked up by its real name), producing a false
    # "Impossible layout" conflict.
    state = parse_and_dispatch(b"struct task_group { atomic_long_t load_avg ____cacheline_aligned; };")
    assert [f.field_name for f in state.fields] == ["load_avg"]
    assert state.fields[0].field_type.original_type == "atomic_long_t"


def test_prefix_annotation_macro_does_not_override_a_real_declarator() -> None:
    # Regression: a macro placed *before* a proper declarator (`__rcu` on an
    # RCU-protected pointer, e.g. `struct css_set __rcu *cgroups;`) also
    # produces a tree-sitter ERROR sibling for the unrecognized macro token
    # -- but unlike the trailing-macro case above, the declarator tree-sitter
    # finds here (`*cgroups`) is already correct and must not be replaced by
    # the ERROR-recovered token. First attempt at fixing the trailing-macro
    # case regressed this exact pattern (every real vmlinux __rcu-annotated
    # field, e.g. task_struct's real_parent/cred/cgroups/sighand, lost its
    # name and reported "struct X __rcu" with nothing after it).
    state = parse_and_dispatch(b"struct task_struct { struct css_set __rcu *cgroups; };")
    assert [f.field_name for f in state.fields] == ["cgroups"]
    assert state.fields[0].field_type.original_type == "struct css_set *"


def test_plain_multi_declarator_field() -> None:
    state = parse_and_dispatch(b"struct foo { int a, b, c; };")
    assert [f.field_name for f in state.fields] == ["a", "b", "c"]
    assert {f.field_type.original_type for f in state.fields} == {"int"}


def test_multiple_declarators_of_a_recursively_resolved_struct(kernel_dir: Path) -> None:
    source = b"struct inner { int x; };\nstruct outer { struct inner *a, *b; };\n"
    (kernel_dir / "foo.h").write_bytes(source)
    build_struct_location_cache()

    node, _ = find_struct_declaration("outer")
    state = KconfigParserState(recursive=True)
    dispatch.dispatch(node, state)

    fields = {f.field_name: f for f in state.fields}
    assert fields["a"].field_type.layout is not None
    assert fields["b"].field_type.layout is not None
    assert [f.field_name for f in fields["a"].field_type.layout.fields] == ["x"]


def test_unresolvable_nested_struct_is_skipped_not_fatal(kernel_dir: Path) -> None:
    # "bar" is referenced but never defined anywhere -- this must not crash the
    # whole recursive parse, just leave that one field's layout unresolved.
    (kernel_dir / "foo.h").write_bytes(b"struct outer { struct bar missing; int after; };\n")
    build_struct_location_cache()

    node, _ = find_struct_declaration("outer")
    state = KconfigParserState(recursive=True)
    dispatch.dispatch(node, state)

    fields = {f.field_name: f for f in state.fields}
    assert fields["missing"].field_type.layout is None
    assert fields["after"].field_type.original_type == "int"
