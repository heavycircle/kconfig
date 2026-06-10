from __future__ import annotations

import re
from typing import TYPE_CHECKING

from kconfig.core import utils
from kconfig.exceptions import KconfigASTAnomalyError
from kconfig.types import KconfigCustomMembers

from .query import run_node_query


if TYPE_CHECKING:
    from tree_sitter import Node


def parse_preproc_if(preproc_node: Node) -> list[str]:
    """Parse a preproc_if node."""
    configs: list[str] = []

    if preproc_node.type in ("preproc_ifdef", "preproc_ifndef"):
        name_node = preproc_node.child_by_field_name("name")
        if not name_node:
            raise KconfigASTAnomalyError(preproc_node.type, "Missing 'name'")

        text = name_node.text.decode()
        if text.startswith("CONFIG_"):
            configs.append(text)

    if preproc_node.type in ("preproc_if", "preproc_elif"):
        print(preproc_node, end="\n\n")
        condition_node = preproc_node.child_by_field_name("condition")
        if not condition_node:
            raise KconfigASTAnomalyError(preproc_node.type, "Missing 'condition'")

        text = condition_node.text.decode()
        configs.extend(re.findall(r"(CONFIG_[A-Za-z0-9_]+)", text))

    return configs


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

        if current.type.startswith("preproc_"):
            configs.extend(parse_preproc_if(current))

        current = current.parent

    return configs


def get_true_type(type_node: Node, field_identifier: Node) -> str:
    """Re-construct the full C type by walking up the declarator chain.

    Appends pointer (``*``), array (``[]``), and function-pointer (``()``)
    modifiers to ``base_type`` based on the node's ancestor declarators.

    Args:
        node (Node): Declarator node whose ancestors are inspected.
        base_type (str): The raw type name (e.g. ``"unsigned int"``).

    Returns:
        str: Full reconstructed type (e.g. ``"unsigned int *"``).

    """
    base_type = type_node.text.decode()

    modifiers: list[str] = []
    current = field_identifier.parent
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


def is_direct_member(field_node: Node, root_node: Node) -> bool:
    """Ensures the field belongs directly to the root struct, not a nested inline one."""
    current = field_node.parent
    while current is not None:
        if current.type in ("struct_specifier", "union_specifier"):
            return current == root_node
        current = current.parent

    return False


def is_primitive_type(field_node: Node) -> bool:
    """Check if a field_node is a primitive type."""
    return field_node.type not in ("primitive_type", "sized_type_specifier")


def get_field_identifier(field_node: Node) -> Node | None:
    """Get the field_identifier from a field node."""
    to_check = [field_node]
    while to_check:
        current = to_check.pop(0)
        if current.type == "field_identifier" and current.text:
            return current

        to_check.extend(current.children)

    return None


def get_type_identifier(field_node: Node) -> Node | None:
    """Get the type_identifier from a field node."""
    to_check = [field_node]
    while to_check:
        current = to_check.pop(0)
        if current.type == "type_identifier" and current.text:
            return current

        to_check.extend(current.children)

    return None
