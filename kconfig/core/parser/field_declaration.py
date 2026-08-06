from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kconfig.core.structs import find_struct_declaration
from kconfig.exceptions import KconfigASTAnomalyError, KconfigSymbolNotFoundError
from kconfig.types import KconfigFieldType, KconfigParserState, KconfigStruct
from kconfig.ui import ui

from .dispatcher import NodeDispatch, dispatch

if TYPE_CHECKING:
    from tree_sitter import Node


STRUCT_MEMO_CACHE: dict[str, KconfigStruct] = {}

ANONYMOUS_FIELD_PREFIX = "anonymous_"
"""Synthetic field name for a declarator-less member (``struct { ... };`` with
no variable name at all) -- guaranteed to never match any real field name a
compiled module could report, since it's a parser-internal placeholder."""


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


def _resolve_named_struct(type_node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> KconfigStruct | None:
    name_node = type_node.child_by_field_name("name")
    if not name_node or not name_node.text:
        raise KconfigASTAnomalyError(type_node.type, "Missing 'name' field")
    struct_name = name_node.text.decode()

    if struct_name in state.visited:
        return None

    if struct_name in STRUCT_MEMO_CACHE:
        return STRUCT_MEMO_CACHE[struct_name]

    try:
        nested_node, nested_struct = find_struct_declaration(struct_name)
    except KconfigSymbolNotFoundError as e:
        ui.out_warning(f"{e}, leaving unresolved ...")
        return None

    branch_visited = state.visited | {struct_name}
    nested_state = KconfigParserState(configs=state.configs, visited=branch_visited, recursive=state.recursive)

    dispatcher.dispatch(nested_node, nested_state)
    nested_struct.fields = nested_state.fields
    STRUCT_MEMO_CACHE[struct_name] = nested_struct
    return nested_struct


def _resolve_layout(type_node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> KconfigStruct | None:
    """Resolve the struct/union layout a field's type points to, if any.

    Computed once per field_declaration and shared across every declarator it
    has -- a field_declaration can declare several fields off one type
    (``struct list_head *next, *prev;``), and an anonymous struct/union body
    isn't memoized anywhere else (it has no name to key a cache on), so
    resolving it per-declarator instead of once would re-parse and re-dispatch
    its body once per declarator, compounding multiplicatively with nesting depth.
    """
    if type_node.type not in ("struct_specifier", "union_specifier"):
        return None

    body_node = type_node.child_by_field_name("body")
    if not body_node:
        return _resolve_named_struct(type_node, state, dispatcher)

    # Anonymous struct/union: its body is inline, so there's nothing to look up.
    # It has no name to key a cache/analysis lookup on either, so it's left out
    # of both (KconfigStruct.original_name == "").
    nested_state = KconfigParserState(configs=state.configs, visited=state.visited, recursive=state.recursive)
    dispatcher.dispatch(body_node, nested_state)
    return KconfigStruct("", Path(), type_node.start_point[0] + 1, fields=nested_state.fields)


def _parse_declarator(
    node: Node, type_node: Node, declarator_node: Node | None, layout: KconfigStruct | None, state: KconfigParserState
) -> None:
    """Record one field, attaching the (already-resolved) shared layout if any."""
    if not type_node.text:
        raise KconfigASTAnomalyError(type_node.type, "Missing type text")

    if declarator_node is None:
        mods, name = "", f"{ANONYMOUS_FIELD_PREFIX}{node.id}"
    else:
        mods, name = unwrap_declarator(declarator_node)

    full_type = " ".join(f"{type_node.text.decode()} {mods}".strip().split())
    field_ref = state.record_field(name, KconfigFieldType(full_type))
    if layout is not None:
        field_ref.field_type.layout = layout


@dispatch.register("field_declaration")
def parse_field_declaration(node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> None:
    """Parse a ``field_declaration`` node.

    A single field_declaration can declare several fields sharing one base
    type (``struct list_head *next, *prev;``), so every declarator attached
    to this node is processed, not just the first.

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

    layout = _resolve_layout(type_node, state, dispatcher) if state.recursive else None

    declarator_nodes = node.children_by_field_name("declarator")
    if not declarator_nodes:
        _parse_declarator(node, type_node, None, layout, state)
        return

    for declarator_node in declarator_nodes:
        _parse_declarator(node, type_node, declarator_node, layout, state)
