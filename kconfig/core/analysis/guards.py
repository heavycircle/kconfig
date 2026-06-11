from __future__ import annotations

import re

import sympy

from kconfig.ui import ui


def parse_config_guard(guard_expr: str) -> sympy.Basic:
    """Convert a C preprocessor condition into a Sympy boolean expression."""
    if not guard_expr:
        return sympy.true

    safe_expr = guard_expr
    safe_expr = re.sub(r"\s*==\s*", "_EQ_", safe_expr)
    safe_expr = re.sub(r"\s*!=\s*", "_NEQ_", safe_expr)
    safe_expr = re.sub(r"\s*>=\s*", "_GTE_", safe_expr)
    safe_expr = re.sub(r"\s*<=\s*", "_LTE_", safe_expr)
    safe_expr = re.sub(r"\s*>\s*", "_GT_", safe_expr)
    safe_expr = re.sub(r"\s*<\s*", "_LT_", safe_expr)

    try:
        py_expr = safe_expr.replace("||", "|").replace("&&", "&").replace("!", "~")
        return sympy.parse_expr(py_expr)
    except (TypeError, ValueError):
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", safe_expr).strip("_")
        ui.out_debug(f"Sympy failed: '{guard_expr}'. Falling back to: {clean_name}")
        return sympy.Symbol(clean_name)


def simplify_config_expression(expr: str) -> str:
    """Parse a CONFIG expressions and simplify as much as possible."""
    try:
        simple = sympy.simplify_logic(parse_config_guard(expr))
        return str(simple).replace("&", "&&").replace("|", "||")
    except TypeError:
        ui.out_warning(f"Cannot simplify: {expr}")
        return expr
