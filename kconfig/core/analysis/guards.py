from __future__ import annotations

import re
from typing import TYPE_CHECKING

import sympy

from kconfig.ui import ui


def parse_config_guard(guard_expr: str) -> sympy.Basic:
    """Convert a C preprocessor condition into a Sympy boolean expression."""
    if not guard_expr:
        return sympy.true
        
    safe_expr = guard_expr
    safe_expr = re.sub(r'\s*==\s*', '_EQ_', safe_expr)
    safe_expr = re.sub(r'\s*!=\s*', '_NEQ_', safe_expr)
    safe_expr = re.sub(r'\s*>=\s*', '_GTE_', safe_expr)
    safe_expr = re.sub(r'\s*<=\s*', '_LTE_', safe_expr)
    safe_expr = re.sub(r'\s*>\s*', '_GT_', safe_expr)
    safe_expr = re.sub(r'\s*<\s*', '_LT_', safe_expr)

    try:
        py_expr = safe_expr.replace("||", "|").replace("&&", "&").replace("!", "~")
        return parse_expr(py_expr)
    except Exception as e:
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', safe_expr).strip('_')
        ui.out_debug(f"Sympy failed: '{c_expr}'. Falling back to: {clean_name}")
        return sympy.Symbol(clean_name)
