from __future__ import annotations

import re
from typing import TYPE_CHECKING

from kconfig.core import utils
from kconfig.utils import KconfigASTAnomalyError, KconfigCustomMembers

from .query import run_node_query


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


def get_custom_members(source: Node) -> KconfigCustomMembers:
    """Get custom members from code.

    This method works for many types of code, but is most often used in this
    application for function signatures and struct definitions.

    Args:
        source (Node): Code to parse for return.

    Returns:
        KconfigCustomMembers: Custom members for this code.

    """
    structs, unions, typedefs = set[str](), set[str](), set[str]()
    captures = run_node_query(source, "signature-match")
    structs.update(utils.get_node_text(n).decode() for n in captures.get("struct.name", []))
    unions.update(utils.get_node_text(n).decode() for n in captures.get("union.name", []))
    typedefs.update(utils.get_node_text(n).decode() for n in captures.get("typedef.name", []))

    typedefs = typedefs - structs - unions
    return KconfigCustomMembers(structs, unions, typedefs)
