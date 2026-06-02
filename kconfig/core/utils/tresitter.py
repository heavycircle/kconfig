from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from tree_sitter import Node


def parse_field_declaration(node: Node) -> dict[str, str]:
    result: dict[str, str] = {}

    type_node = field_node.child_by_field_name("type")
    if not type_node or not type_node.text:
        return result
        
    base_type = type_node.text.decode("utf-8").strip()
    for child in field_node.children:
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
    """Parse a field_declaration_list and return a field dictionary."""
    layout: dict[str, str] = {}

    if body_node.type != "field_declaration_list":
        raise ValueError(f"Expected field_declaration_list, got {body_node.type}")
        
    for child in body_node.children:
        if child.type == "field_declaration":
            fields_dict = parse_field_declaration(child)
            layout.update(fields_dict)
            
    return layout
