from __future__ import annotations

import re
from typing import TYPE_CHECKING

from kconfig.utils import KconfigAstAnomalyError


if TYPE_CHECKING:
    from tree_sitter import Node


def get_enclosing_configs(node: Node) -> list[str]:
    """Walk up the AST to find all #ifdef locking this field.

    Args:
        node (Node): Base node to walk.

    Returns:
        list[str]: CONFIG options locking this node.

    """
    configs: list[str] = []

    current = node.parent
    while current is not None:
        if current.type in ("struct_specifier", "union_specifier"):  # NOTE: Might need to remove union_specifier
            break

        if current.type in ("preproc_ifdef", "preproc_if"):
            if not current.text:
                raise KconfigASTAnomalyError(current.type, "Missing body")

            text = current.text.decode()
            match = re.search(r"(CONFIG_[A-Za-z0-9]+)", text)
            if match:
                configs.insert(0, match.group(1))

        current = current.parent

    return configs


def get_true_type(node: Node, base_type: str) -> str:
    """Re-construct pointer and array types."""
    modifiers: list[str] = []

    current = node.parent
    while current is not None:
        if current.type == "field_declaration":
            break

        if current.type == "pointer_declarator":
            modifiers.append("*")
        if current.type == "array_declarator":
            modifiers.append("[]")
        if current.type == "function_declarator":
            modifiers.append("()")

        current = current.parent

    modifier = "".join(modifiers)
    return f"{base_type} {modifier}".strip()
