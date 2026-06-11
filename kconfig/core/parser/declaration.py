from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.structs.kernel import find_struct_declaration
from kconfig.exceptions import KconfigASTAnomalyError, KconfigInvalidArgumentError, KconfigSymbolNotFoundError
from kconfig.types import KconfigFieldType, KconfigStruct, KconfigStructField
from kconfig.ui import ui

from .utils import (
    get_enclosing_configs,
    get_field_identifier,
    get_true_type,
    get_type_identifier,
    is_primitive_type,
)


if TYPE_CHECKING:
    from pathlib import Path

    from tree_sitter import Node


STRUCT_LAYOUT_CACHE: dict[str, KconfigStruct] = {}


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
        if type_node.type in ("struct_specifier", "union_specifier") and has_body:
            # TODO: struct_specifier should never hit here
            base_name = f"anonymous {type_node.type.split('_')[0]}"
            ui.out_debug(f" >> Recursing into {base_name}: unnamed")

            anonymous_field = KconfigStruct(f"<{base_name}>", f"<{base_name}>", decl_path)
            anonymous_field.fields = parse_struct_specifier(type_node, decl_path, recursive, visited)
            type_layout = KconfigFieldType(base_name)
            type_layout.layout = anonymous_field

            configs = get_enclosing_configs(field_node)
            return [KconfigStructField("<anonymous>", type_layout, depends=configs)]

        # No declarator and not inline -> must be bad
        return []

    fields: list[KconfigStructField] = []
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

                anonymous_field = KconfigStruct(f"<{base_name}>", f"<{base_name}>", decl_path)
                anonymous_field.fields = parse_struct_specifier(type_node, decl_path, recursive, visited)
                type_layout = KconfigFieldType(base_name)
                type_layout.layout = anonymous_field

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
    fields: list[Node] = []
    for child in node.children:
        if child.type == "field_declaration":
            fields.append(child)
        elif child.type.startswith("preproc_"):
            fields.extend(_get_direct_fields(child))

    return fields


def parse_field_declaration_list(
    root_node: Node, root_name: str, decl_path: Path, recursive: bool, visited: set[str] | None = None
) -> list[KconfigStructField]:
    """Parse a field_declaration_list to get the types underneath."""
    if root_node.type != "field_declaration_list":
        raise KconfigInvalidArgumentError(root_node.type, "Not a field_declaration_list")

    if visited is None:
        visited = set()

    field_layout: list[KconfigStructField] = []
    for child in _get_direct_fields(root_node):
        fields = parse_field_declaration(child, decl_path, recursive, visited)
        if not fields:
            ui.out_warning(f"Failed to resolve field in '{root_name}': {child.text.decode()}")

        field_layout.extend(fields)

    return field_layout


def parse_struct_specifier(
    root_node: Node, decl_path: Path, recursive: bool, visited: set[str] | None = None
) -> list[KconfigStructField]:
    """Parse a struct_specifier node."""
    if root_node.type not in ("struct_specifier", "union_specifier"):
        raise KconfigInvalidArgumentError(root_node.type, "Not a struct_specifier or union_specifier")

    name_node = root_node.child_by_field_name("name")
    name = name_node.text.decode() if name_node else f"anonymous {root_node.type.split('_')[0]}"

    body_node = root_node.child_by_field_name("body")
    if not body_node:
        raise KconfigASTAnomalyError(root_node.type, "Missing name and body")

    return parse_field_declaration_list(body_node, name, decl_path, recursive, visited)


def get_kernel_struct(
    struct_name: str, recursive: bool = False, active_chain: set[str] | None = None
) -> KconfigStruct | None:
    """Find configs inside a structure."""
    if active_chain is None:
        active_chain = set()

    if struct_name in STRUCT_LAYOUT_CACHE:
        ui.out_debug(f"Cache hit: '{struct_name}'")
        return STRUCT_LAYOUT_CACHE[struct_name]

    if struct_name in active_chain:
        ui.out_debug(f"Already parsed: {struct_name}")
        return None
    visited.add(struct_name)

    try:
        root_node, struct_info = find_struct_declaration(struct_name)
        struct_info.fields = parse_struct_specifier(root_node, struct_info.file, recursive, visited)
        STRUCT_LAYOUT_CACHE[struct_name] = struct_info
        return struct_info
    except KconfigSymbolNotFoundError:
        ui.out_warning(f"Cannot find definition for '{struct_name}'")
        return None
    finally:
        active_chain.remove(struct_name)
