from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.utils import NodeDispatch, dispatcher
from kconfig.exceptions import KconfigASTAnomalyError

from .condition import parse_condition_node

if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigParserState


@dispatcher.register("preproc_def")
def parse_preproc_def(node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> None:
    """Parse a ``preproc_def`` node.

    Args:
            node (Node): The tree-sitter node to process.
            state (KconfigParserState): The current state of processing.
            dispatcher (NodeDispatch): The dispatcher to call child nodes.

    Raises:
            KconfigASTAnomalyError: Node is missing 'condition' field.

    """
    print(node)
    field_name = "condition" if node.type == "preproc_if" else "name"

    config_expr = node.child_by_field_name(field_name)
    if not config_expr:
        raise KconfigASTAnomalyError(node.type, f"Missing '{field_name}' field!")

    state.push_config(parse_condition_node(config_expr))
    for child in node.children:
        dispatcher.dispatch(child, state)
    state.pop_config()
