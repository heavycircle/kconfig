from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.structs import find_struct_declaration
from kconfig.exceptions import KconfigASTAnomalyError
from kconfig.types import KconfigFieldType, KconfigParserState, KconfigStruct

from .dispatcher import NodeDispatch, dispatch

if TYPE_CHECKING:
    from tree_sitter import Node


STRUCT_MEMO_CACHE: dict[str, KconfigStruct] = {}


def unwrap_declarator(node: Node) -> tuple[str, str]:
    """Dig into a declarator node to separate a name from the type modifiers.

    This method intentionally does not attempt to parse ``function_declarator``
    nodes. They show up almost identically inside ``pahole``.

    Args:
        node (Node): The tree-sitter node to process.

    Raises:
        KconfigASTAnomalyError: Declarators missing ``declarator`` field.

    Returns:
        tuple[str, str]: A tuple contianing (modifiers, name).

    """
    if not node.text:
        return "", ""

    match node.type:
        case "pointer_declarator":
            nested = node.child_by_field_name("declarator")
            if not nested:
                raise KconfigASTAnomalyError(node.type, "Missing 'declarator' field")
            mods, name = unwrap_declarator(nested)

            mods = f"*{mods}"
        case "array_declarator":
            nested = node.child_by_field_name("declarator")
            if not nested:
                raise KconfigASTAnomalyError(node.type, "Missing 'declarator' field")
            mods, name = unwrap_declarator(nested)

            size_node = node.child_by_field_name("size")
            size_str = f"[{size_node.text.decode()}]" if size_node and size_node.text else "[]"
            mods = f"{mods}{size_str}"
        case _:  # Fallback: No type modifiers (identifier, field_identifier, function_declarator, ...)
            mods, name = "", node.text.decode()

    return mods, name


@dispatch.register("field_declaration")
def parse_field_declaration(node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> None:
    """Parse a ``field_declaration`` node.

    This method records the current node inside the current state. Reaching a
    field_declaration means we've reached a field of the structure.

    Args:
        node (Node): The tree-sitter node to process.
        state (KconfigParserState): The current state of processing.
        dispatcher (NodeDispatch): The dispatcher to call child nodes.

    Raises:
        KconfigASTAnomalyError: Node is missing a type field.

    """
    type_node = node.child_by_field_name("type")
    if not type_node or not type_node.text:
        raise KconfigASTAnomalyError(node.type, "Missing 'type' field")
    base_type = type_node.text.decode()

    declarator_node = node.child_by_field_name("declarator")
    if not declarator_node:
        mods, name = "", f"anonymous_{node.id}"
    else:
        mods, name = unwrap_declarator(declarator_node)

    full_type = " ".join(f"{base_type} {mods}".strip().split())
    field_type = KconfigFieldType(full_type)
    field_ref = state.record_field(name, field_type)

    if not state.recursive:
        return

    if type_node.type in ("struct_specifier", "union_specifier"):
        body_node = type_node.child_by_field_name("body")
        if not body_node:
            # Struct defined elsewhere - to the beginning.
            name_node = type_node.child_by_field_name("name")
            if not name_node or not name_node.text:
                raise KconfigASTAnomalyError(type_node.type, "Missing 'name' field")
            struct_name = name_node.text.decode()

            if struct_name in state.visited:
                return

            if struct_name in STRUCT_MEMO_CACHE:
                field_ref.field_type.layout = STRUCT_MEMO_CACHE[struct_name]
                return

            nested_node, nested_struct = find_struct_declaration(name_node.text.decode())
            branch_visited = state.visited | {struct_name}
            nested_state = KconfigParserState(configs=state.configs, visited=branch_visited, recursive=state.recursive)

            dispatcher.dispatch(nested_node, nested_state)
            nested_struct.fields = nested_state.fields
            field_ref.field_type.layout = nested_struct
            STRUCT_MEMO_CACHE[struct_name] = nested_struct
