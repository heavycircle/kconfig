from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.utils import NodeDispatch, dispatcher
from kconfig.exceptions import KconfigASTAnomalyError

from .condition import parse_condition_node

if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigParserState


@dispatcher.register("type_definition")
def parse_type_definition(node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> None:
    """Parse a ``type_definition`` node.

    Args:
            node (Node): The tree-sitter node to process.
            state (KconfigParserState): The current state of processing.
            dispatcher (NodeDispatch): The dispatcher to call child nodes.

    Raises:
            KconfigASTAnomalyError: Node is missing 'condition' field.

    """
    print(node)
