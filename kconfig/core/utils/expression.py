from __future__ import annotations

from sympy import parse_expr, simplify_logic

from kconfig.ui import ui


def simplify_config_expression(expr: str) -> str:
    """Parse a CONFIG expressions and simplify as much as possible."""
    try:
        line = expr.replace("&&", "&").replace("||", "|")
        simple = simplify_logic(parse_expr(line))
        return str(simple).replace("&", "&&").replace("|", "||")
    except TypeError:
        ui.out_warning(f"Cannot simplify: {expr}")
        return expr
