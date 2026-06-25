from __future__ import annotations

from collections.abc import Callable

from tree_sitter import Node

from kconfig.types import KconfigParserState

DispatchFunc = Callable[[Node, KconfigParserState, "NodeDispatch"], None]
"""Type of the calling dispatch function."""


class NodeDispatch:
    """Recursively dispatch tree-sitter nodes for processing."""

    def __init__(self) -> None:
        self._handlers: dict[str, DispatchFunc] = {}

    def register(self, node_type: str) -> Callable[[DispatchFunc], DispatchFunc]:
        """Register a handler for dispatching a specific node type."""

        def decorator(func: DispatchFunc) -> DispatchFunc:
            self._handlers[node_type] = func
            return func

        return decorator

    def dispatch(self, node: Node, state: KconfigParserState) -> None:
        """Dispatch a specific node type to its handler, if it exists."""
        handler = self._handlers.get(node.type)
        if handler:
            handler(node, state, self)
        else:
            for child in node.children:
                self.dispatch(child, state)


# Singleton instance
dispatcher = NodeDispatch()
