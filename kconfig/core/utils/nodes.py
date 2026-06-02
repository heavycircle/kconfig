from __future__ import annotations

from typing import TYPE_CHECKING, cast

from kconfig.utils import KconfigQueryImpossibleError, KconfigQueryNoMatchError


if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.utils import KconfigQueryCapture


def get_capture_nodes(captures: KconfigQueryCapture, key: str) -> list[Node]:
    """Get all nodes matching a query string.

    Args:
        captures (KconfigQueryCapture): Capture from a KconfigQueryResult.
        key (str): Key to find.

    Raises:
        KconfigQueryNoMatchError: Key not found.
        KconfigQueryImpossibleError: Missing text from query.

    Returns:
        list[Node]: List of nodes found.

    """
    nodes = captures.get(key)
    if not nodes:
        raise KconfigQueryNoMatchError(f"Key not found: {key}")
    if not all(n.text for n in nodes):
        raise KconfigQueryImpossibleError(f"Missing text in node {getattr(nodes, 'type', 'Unknown')}")

    return nodes


def get_capture_text(captures: KconfigQueryCapture, key: str) -> list[bytes]:
    """Get all text from a capture.

    Args:
        captures (KconfigQueryCapture): Capture from a KconfigQueryResult.
        key (str): Key to find.

    Returns:
        list[bytes]: Retrieved node from result.

    """
    return [cast("bytes", n.text) for n in get_capture_nodes(captures, key)]


def get_node_text(node: Node | None) -> bytes:
    """Get the value of a single node.

    Args:
        node (Node | None): Node to parse.

    Raises:
        KconfigQueryImpossibleError: Missing contents of the structure.

    Returns:
        bytes: Retrieved item text.

    """
    if node is None or not node.text:
        raise KconfigQueryImpossibleError(f"Missing text from {getattr(node, 'type', 'Unknown')}")
    return node.text
