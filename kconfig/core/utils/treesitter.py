from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser
from kconfig.utils import KconfigQueryImpossibleError

from .nodes import get_capture_nodes


if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.utils import KconfigStruct


def parse_field_declaration(node: Node) -> dict[str, str]:
    """Parse a field_declaration and return a field dictionary.

    Args:
        node (Node): Base node of the field declaration.

    Returns:
        dict[str, str]: Dictionary of {name: type} objects.

    """
    result: dict[str, str] = {}

    type_node = node.child_by_field_name("type")
    if not type_node or not type_node.text:
        return result

    base_type = type_node.text.decode("utf-8").strip()
    for child in node.children:
        if child == type_node or not child.is_named:
            continue

        decl_text = child.text.decode("utf-8").strip() if child.text else ""

        # Find the actual name inside the declarator
        name = ""
        nodes_to_check = [child]
        while nodes_to_check:
            current = nodes_to_check.pop(0)
            if current.type == "field_identifier" and current.text:
                name = current.text.decode("utf-8")
                break
            nodes_to_check.extend(current.children)

        if not name:
            continue

        # Construct the full C type
        modifiers = decl_text.replace(name, "").strip()
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
        raise ValueError(f"Expected field_declaration_list, got {node.type}")

    for child in node.children:
        if child.type == "field_declaration":
            fields_dict = parse_field_declaration(child)
            layout.update(fields_dict)

    return layout


def get_struct_members(struct: KconfigStruct) -> dict[str, str]:
    """Get the members of a structure."""
    query = parser.get_query("struct-find").replace("__STRUCT_NAME__", struct.name)

    module_fields: dict[str, str] = {}
    for _, captures in parser.run_query(struct.body, query):
        nodes = get_capture_nodes(captures, "struct.body")
        if len(nodes) != 1:
            raise KconfigQueryImpossibleError(f"More than one structure found: {struct.name}")

        module_fields = parse_field_declaration_list(nodes[0])

    if not module_fields:
        raise KconfigQueryImpossibleError(f"No members found in {struct.name}")
    return module_fields
