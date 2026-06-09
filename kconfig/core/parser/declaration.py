from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.structs.kernel import find_struct_declaration
from kconfig.exceptions import KconfigASTAnomalyError, KconfigInvalidArgumentError
from kconfig.styling_api import ui
from kconfig.types import KconfigFieldType, KconfigStruct, KconfigStructField

from .utils import get_enclosing_configs, get_field_identifier, get_true_type, get_type_identifier, is_primitive_type


if TYPE_CHECKING:
    from pathlib import Path

    from tree_sitter import Node


def parse_field_declaration(
    field_node: Node, decl_path: Path, recursive: bool, visited: set[str] | None = None
) -> list[KconfigStructField]:
    """Parse a field_declaration node."""
    if field_node.type != "field_declaration":
        raise KconfigInvalidArgumentError(field_node.type, "Not a field_declaration")

    # All field_declarations have type fields.
    type_node = field_node.child_by_field_name("type")
    if not type_node:
        return []

    declarators = field_node.children_by_field_name("declarator")
    if not declarators:
        # Structure with a body -> anonymous
        has_body = type_node.child_by_field_name("body")
        if type_node.type in ("struct_specifier", "union_specifier") and has_body:  # TODO: struct_specifier should never hit here
            base_name = f"anonymous {type_node.type.split('_')[0]}"
            ui.out_debug(f" >> Recursing into {base_name}")

            type_layout = KconfigFieldType(base_name)
            type_layout.layout = parse_struct_specifier(type_node, decl_path, recursive, visited)

            configs = get_enclosing_configs(field_node)
            return [KconfigStructField("<anonymous>", type_layout, depends=configs)]

        # No declarator and not inline -> must be bad
        return []

    fields = []
    for decl_node in declarators:
        # Get the base field_identifier.
        field_identifier = get_field_identifier(decl_node)
        if not field_identifier:
            return []

        # Re-construct its true type.
        field_type = get_true_type(type_node, field_identifier)
        field_name = field_identifier.text.decode()

        type_layout = KconfigFieldType(field_type)
        if type_node.type in ("struct_specifier", "union_specifier"):
            # Check for anonymous structs/unions with declarators.
            if type_node.child_by_field_name("body") is not None:
                base_type = f"anonymous {type_node.type.split('_')[0]}"
                ui.out_debug(f" >> Recursing into {base_type}: {field_name}")

                type_layout = KconfigFieldType(base_type)
                type_layout.layout = parse_struct_specifier(type_node, decl_path, recursive, visited)

                configs = get_enclosing_configs(field_node)
                return [KconfigStructField(field_name, type_layout, depends=configs)]

            # Get the name of this type.
            type_name = get_type_identifier(type_node)
            if not type_name:
                return []

            # Make a recursive call.
            if recursive:
                ui.out_debug(f" >> Recursing into custom field: {type_node.text.decode()}")
                type_layout.layout = get_kernel_struct(type_name.text.decode(), recursive, visited)

        # Non-structures that aren't primitive types are custom types.
        elif not is_primitive_type(type_node):
            ui.out_debug(f" >> Found typedef: {type_node.text.decode()} {field_name}")

        # Get configs enclosing these fields.
        configs = get_enclosing_configs(field_node)
        fields.append(KconfigStructField(field_name, type_layout, depends=configs))

    return fields


def _get_direct_fields(node: Node) -> list[Node]:
    fields = []
    for child in current.children:
        if child.type == "field_declaration":
            fields.append(child)
        elif child.type.startswith("preproc_"):
            fields.extend(_get_direct_fields(child))

    return fields

def parse_field_declaration_list(
    field_node: Node, decl_path: Path, recursive: bool, visited: set[str] | None = None
) -> list[KconfigStructField]:
    """Parse a field_declaration_List to get the types underneath."""
    if root_node.type != "field_declaration_list":
        raise KconfigInvalidArgumentError(root_node.type, "Not a field_declaration_list")

    if visited is None:
        visited = set()

    field_layout = []
    for child in _get_direct_fields(root_node):
        fields = parse_field_declaration(child, decl_path, recursive, visited)
        if not fields:
            ui.out_warning(f"Failed to resolve field: {child.text.decode()}")

        field_layout.extend(fields)

    return field_layout


def parse_struct_specifier(
    root_node: Node, decl_path: Path, recursive: bool, visited: set[str] | None = None
) -> KconfigStruct:
    """Parse a struct_specifier node."""
    if root_node.type != "struct_specifier":
        raise KconfigInvalidArgumentError(root_node.type, "Not a struct_specifier")

    name_node = root_node.child_by_field_name("name")
    name = name_node.text.decode() if name_node else f"anonymous {root_node.type.split('_')[0]}"

    body_node = root_node.child_by_field_name("body")
    if not body_node:
        raise KconfigASTAnomalyError(root_node.type, "Missing name and body")

    struct_layout = KconfigStruct(name, decl_path)
    struct_layout.fields = parse_field_declaration_list(body_node, decl_path, recursive, visited)
    return struct_layout


def get_kernel_struct(struct_name: str, recursive: bool = False, visited: set[str] | None = None) -> KconfigStruct | None:
    """Find configs inside a structure."""
    if visited is None:
        visited = set()

    if struct_name in visited:
        ui.out_debug(f"Already parsed: {struct_name}")
        return None
    visited.add(struct_name)

    root_node, path = find_struct_declaration(struct_name)
    return parse_struct_specifier(root_node, path, recursive, visited)
