from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.utils import NodeDispatch, dispatcher

if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigParserState


@dispatcher.register("preproc_else")
def parse_preproc_else(node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> None:
    """Parse a ``preproc_else`` node.

    This method negates the previous config (coming from a ``#if`` or ``#elif``)
    and dispatches the children for processing.

    Args:
            node (Node): The tree-sitter node to process.
            state (KconfigParserState): The current state of processing.
            dispatcher (NodeDispatch): The dispatcher to call child nodes.

    """
    # Negate the config before this before dispatching.
    state.negate_last_config(node.type)

    for child in node.children:
        dispatcher.dispatch(child, state)

