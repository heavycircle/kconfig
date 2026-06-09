from __future__ import annotations

from typing import TYPE_CHECKING, cast

from kconfig.exceptions import KconfigASTAnomalyError


if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigQueryCapture


def get_capture_nodes(captures: KconfigQueryCapture, key: str) -> list[Node]:
    """Get all nodes matching a query string.

    Args:
        captures (KconfigQueryCapture): Capture from a KconfigQueryResult.
        key (str): Key to find.

    Raises:
        KconfigASTAnomalyError: Capture group missing from query results.
        KconfigASTAnomalyError: Missing text from query.

    Returns:
        list[Node]: List of nodes found.

    """
    nodes = captures.get(key)
    if not nodes:
        raise KconfigASTAnomalyError(key, "Capture group missing from query results.")
    if not all(n.text for n in nodes):
        raise KconfigASTAnomalyError(key, "Some nodes contain no text payload.")

    return nodes


def get_capture_text(captures: KconfigQueryCapture, key: str) -> list[bytes]:
    """Get all text from a capture.

    Args:
        captures (KconfigQueryCapture): Capture from a KconfigQueryResult.
        key (str): Key to find.

    Returns:
        list[bytes]: Text payload of every node matching ``key``.

    """
    return [cast("bytes", n.text) for n in get_capture_nodes(captures, key)]


def get_node_text(node: Node | None) -> bytes:
    """Get the value of a single node.

    Args:
        node (Node | None): Node to parse.

    Raises:
        KconfigASTAnomalyError: Not a tree-sitter node.
        KconfigASTAnomalyError: Node contains no text payload.

    Returns:
        bytes: Retrieved item text.

    """
    if not node:
        raise KconfigASTAnomalyError("None", "Expected tree-sitter node, received None.")
    if not node.text:
        raise KconfigASTAnomalyError(node.type, "Node contains no text payload.")
    return node.text
