from __future__ import annotations

from typing import TYPE_CHECKING

import sympy

from kconfig.exceptions import KconfigASTAnomalyError

from .condition import parse_condition_node
from .dispatcher import NodeDispatch, dispatch

if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigParserState


def _is_header_guard(node: Node, guard_name: str) -> bool:
    """Check if a top-level ``#ifndef NAME`` is a ``NAME_H``-style include guard.

    Header guards (``#ifndef FOO_H`` / ``#define FOO_H`` wrapping the whole
    file) aren't CONFIG conditions, but they parse identically to one. Left
    alone, every field/typedef in the file would pick up the file's own
    include-guard macro as a spurious, ever-present guard term. Since the
    guard is only ever defined by the file itself, it's always true once
    we're inside it, so it's safe to treat as unconditional rather than try
    to track it.

    Args:
        node (Node): The ``preproc_ifdef`` node to check.
        guard_name (str): The identifier following ``#ifndef``.

    Returns:
        bool: True if this is the file's own top-level include guard.

    """
    if node.children[0].type != "#ifndef" or node.parent is None or node.parent.type != "translation_unit":
        return False

    first_define = next((c for c in node.named_children if c.type == "preproc_def"), None)
    define_name = first_define.child_by_field_name("name") if first_define else None
    return bool(define_name and define_name.text and define_name.text.decode() == guard_name)


@dispatch.register("preproc_if")
@dispatch.register("preproc_ifdef")
def parse_preproc_if(node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> None:
    """Parse a ``preproc_if`` or ``preproc_ifdef`` node.

    Args:
            node (Node): The tree-sitter node to process.
            state (KconfigParserState): The current state of processing.
            dispatcher (NodeDispatch): The dispatcher to call child nodes.

    Raises:
            KconfigASTAnomalyError: Node is missing 'condition' field.

    """
    field_name = "condition" if node.type == "preproc_if" else "name"

    config_expr = node.child_by_field_name(field_name)
    if not config_expr or not config_expr.text:
        raise KconfigASTAnomalyError(node.type, f"Missing '{field_name}' field!")

    if node.type == "preproc_ifdef" and _is_header_guard(node, config_expr.text.decode()):
        for child in node.children:
            dispatcher.dispatch(child, state)
        return

    condition = parse_condition_node(config_expr)
    if node.type == "preproc_ifdef" and node.children[0].type == "#ifndef":
        condition = sympy.Not(condition)

    state.push_config(condition)
    for child in node.children:
        dispatcher.dispatch(child, state)
    state.pop_config()
