from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser
from kconfig.exceptions import KconfigASTAnomalyError
from kconfig.types import KconfigStructFields

from .nodes import get_capture_nodes


if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigStruct


def _extract_field_name(node: Node) -> str:
    """Find field_identifier recursively within a declarator node.

    Args:
        node (Node): Root declarator node to search.

    Returns:
        str: The decoded field name, or an empty string if none is found.

    """
    nodes_to_check = [node]
    while nodes_to_check:
        current = nodes_to_check.pop(0)
        if current.type == "field_identifier" and current.text:
            return current.text.decode("utf-8")
        nodes_to_check.extend(current.children)

    return ""


def _get_anonymous_type(node: Node) -> KconfigStructFields:
    """Flatten an anonymous struct or union into a type dictionary.

    Args:
        node (Node): ``struct_specifier`` or ``union_specifier`` node whose
            body contains the anonymous member declarations.

    Returns:
        KconfigStructFields: Mapping of ``{field_name: c_type}`` for all
            fields found in the anonymous body.

    """
    result = KconfigStructFields()

    body_node = node.child_by_field_name("body")
    if body_node:
        for inner_child in body_node.children:
            if inner_child.type == "field_declaration":
                result.update(parse_field_declaration(inner_child))

    return result


def parse_field_declaration(node: Node) -> dict[str, str]:
    """Parse a field_declaration and return a field dictionary.

    Args:
        node (Node): Base node of the field declaration.

    Returns:
        dict[str, str]: Dictionary of {name: type} objects.

    """
    result: dict[str, str] = {}

    type_node = node.child_by_field_name("type")
    if not type_node:
        return result

    # Flatten the AST for anonymous unions
    if type_node.type in ("struct_specifier", "union_specifier"):
        has_declarator = any(child.is_named and child != type_node for child in node.children)
        if not has_declarator:
            return _get_anonymous_type(type_node)

    if not type_node.text:
        return result

    # Parse standard fields
    base_type = type_node.text.decode("utf-8").strip()
    for child in node.children:
        if child == type_node or not child.is_named:
            continue

        # Find the name
        decl_text = child.text.decode("utf-8").strip() if child.text else ""
        name = _extract_field_name(child)
        modifiers = decl_text.replace(name, "").strip()

        # Construct the full C type
        full_type = f"{base_type} {modifiers}".strip()
        full_type = full_type.replace("*", " *").replace("  ", " ").strip()
        result[name] = full_type

    return result


def parse_field_declaration_list(node: Node) -> dict[str, str]:
    """Parse a field_declaration_list and return a field dictionary.

    Args:
        node (Node): Base node of the field declaration list.

    Returns:
        dict[str, str]: Dictionary of {name: type} objects.

    """
    layout: dict[str, str] = {}

    if node.type != "field_declaration_list":
        raise KconfigASTAnomalyError(node.type, "Expected field_declaration_list")

    for child in node.children:
        if child.type == "field_declaration":
            fields_dict = parse_field_declaration(child)
            layout.update(fields_dict)

    return layout


def get_struct_members(struct: KconfigStruct) -> dict[str, str]:
    """Parse a struct's compiled body and return all field names with their types.

    Args:
        struct (KconfigStruct): Struct whose ``body`` bytes will be queried.

    Returns:
        dict[str, str]: Mapping of field name to its C type string.

    """
    module_fields: dict[str, str] = {}
    for _, captures in parser.run_query(struct.body, "struct-list"):
        nodes = get_capture_nodes(captures, "struct.body")
        if len(nodes) != 1:
            raise KconfigASTAnomalyError(struct.name, "More than one structure found")
        module_fields = parse_field_declaration_list(nodes[0])

    return module_fields or {}
