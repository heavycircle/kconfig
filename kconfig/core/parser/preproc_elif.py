from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.utils import NodeDispatch, dispatcher
from kconfig.exceptions import KconfigASTAnomalyError

from .condition import parse_condition_node

if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigParserState


@dispatcher.register("preproc_elif")
def parse_preproc_elif(node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> None:
    """Parse a ``preproc_elif`` node.

    This method negates the previous config (coming from a ``#if`` or another
    ``#elif``) and dispatches the children for processing.

    Args:
            node (Node): The tree-sitter node to process.
            state (KconfigParserState): The current state of processing.
            dispatcher (NodeDispatch): The dispatcher to call child nodes.

    Raises:
            KconfigASTAnomalyError: Node is missing 'condition' field.

    """
    config_expr = node.child_by_field_name("condition")
    if not config_expr:
        raise KconfigASTAnomalyError(node.type, "Missing 'condition' field!")

    # Negate the config before this before dispatching.
    state.negate_last_config(node.type)

    state.push_config(parse_condition_node(config_expr))
    for child in node.children:
        dispatcher.dispatch(child, state)
    state.pop_config()
