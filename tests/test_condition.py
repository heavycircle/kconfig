from __future__ import annotations

import sympy

from kconfig.core.parser.condition import parse_condition_node
from kconfig.core.query.query import parse_source


def _condition_of(source: bytes) -> object:
    root = parse_source(source)
    preproc_if = root.children[0]
    condition = preproc_if.child_by_field_name("condition")
    assert condition is not None
    return condition


def test_bare_identifier_is_a_symbol() -> None:
    node = _condition_of(b"#if CONFIG_FOO\nint x;\n#endif")
    assert parse_condition_node(node) == sympy.Symbol("CONFIG_FOO")


def test_defined_call_syntax() -> None:
    node = _condition_of(b"#if defined(CONFIG_FOO)\nint x;\n#endif")
    assert parse_condition_node(node) == sympy.Symbol("CONFIG_FOO")


def test_defined_without_parens() -> None:
    node = _condition_of(b"#if defined CONFIG_FOO\nint x;\n#endif")
    assert parse_condition_node(node) == sympy.Symbol("CONFIG_FOO")


def test_is_enabled_call_expression() -> None:
    node = _condition_of(b"#if IS_ENABLED(CONFIG_FOO)\nint x;\n#endif")
    assert parse_condition_node(node) == sympy.Symbol("CONFIG_FOO")


def test_logical_and() -> None:
    node = _condition_of(b"#if CONFIG_FOO && CONFIG_BAR\nint x;\n#endif")
    assert parse_condition_node(node) == sympy.And(sympy.Symbol("CONFIG_FOO"), sympy.Symbol("CONFIG_BAR"))


def test_logical_or() -> None:
    node = _condition_of(b"#if CONFIG_FOO || CONFIG_BAR\nint x;\n#endif")
    assert parse_condition_node(node) == sympy.Or(sympy.Symbol("CONFIG_FOO"), sympy.Symbol("CONFIG_BAR"))


def test_logical_not() -> None:
    node = _condition_of(b"#if !CONFIG_FOO\nint x;\n#endif")
    assert parse_condition_node(node) == sympy.Not(sympy.Symbol("CONFIG_FOO"))


def test_parenthesized_expression() -> None:
    node = _condition_of(b"#if (CONFIG_FOO)\nint x;\n#endif")
    assert parse_condition_node(node) == sympy.Symbol("CONFIG_FOO")


def test_unsupported_binary_expression_falls_back_to_a_symbol() -> None:
    node = _condition_of(b"#if CONFIG_FOO == 1\nint x;\n#endif")
    result = parse_condition_node(node)
    assert isinstance(result, sympy.Symbol)


def test_unsupported_unary_expression_falls_back_to_a_symbol() -> None:
    node = _condition_of(b"#if -CONFIG_FOO\nint x;\n#endif")
    result = parse_condition_node(node)
    assert isinstance(result, sympy.Symbol)
