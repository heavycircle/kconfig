from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import utils
from kconfig.types import KconfigCustomMembers, KconfigFieldGuard

from .preprocessor import parse_preproc
from .query import run_node_query


if TYPE_CHECKING:
    from tree_sitter import Node


def get_enclosing_configs(node: Node) -> KconfigFieldGuard | None:
    """Walk up the AST to find all #ifdef locking this field.

    Args:
        node (Node): Base node to walk.

    Returns:
        KconfigFieldGuard: CONFIG options locking this node, else None.

    """
    current = node.parent
    while current is not None:
        if current.type in ("struct_specifier", "union_specifier"):  # NOTE: Might need to remove union_specifier
            break

        if current.type.startswith("preproc_"):
            return parse_preproc(current)

        current = current.parent

    return None


def get_true_type(type_node: Node, field_identifier: Node) -> str:
    """Re-construct the full C type by walking up the declarator chain.

    Appends pointer (``*``), array (``[]``), and function-pointer (``()``)
    modifiers to ``base_type`` based on the node's ancestor declarators.

    Args:
        type_node (Node): The node containing the base type.
        field_identifier (Node): The field_identifier to walk from.

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
    """Ensures the field belongs directly to the root struct, not a nested inline one.

    Args:
        field_node (Node): The field node to start walking from.
        root_node (Node): The root node to compare to.

    Returns:
        bool: True if field_node is a direct member of root_node.

    """
    current = field_node.parent
    while current is not None:
        if current.type in ("struct_specifier", "union_specifier"):
            return current == root_node
        current = current.parent

    return False


def is_primitive_type(field_node: Node) -> bool:
    """Check if a field_node is a primitive type.

    Args:
        field_node (Node): The node to check.

    Returns:
        bool: True if this field_node holds a primitive type.

    """
    return field_node.type not in ("primitive_type", "sized_type_specifier")


def get_field_identifier(field_node: Node) -> Node | None:
    """Get the field_identifier from a field node.

    Args:
        field_node (Node): The base node to parse.

    Returns:
        Node | None: The field_identifier inside field_node, else None if
            field_node doesn't have one.

    """
    to_check = [field_node]
    while to_check:
        current = to_check.pop(0)
        if current.type == "field_identifier" and current.text:
            return current

        to_check.extend(current.children)

    return None


def get_type_identifier(field_node: Node) -> Node | None:
    """Get the type_identifier from a field node.

    Args:
        field_node (Node): The base node to parse.

    Returns:
        Node | None: The type_identifier inside field_node, else None if
            field_node doesn't have one.

    """
    to_check = [field_node]
    while to_check:
        current = to_check.pop(0)
        if current.type == "type_identifier" and current.text:
            return current

        to_check.extend(current.children)

    return None
