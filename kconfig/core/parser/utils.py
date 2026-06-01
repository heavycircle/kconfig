from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.utils import KconfigQueryImpossibleError, KconfigQueryResult


if TYPE_CHECKING:
    from tree_sitter import Node


def get_nodes(result: KconfigQueryResult, name: str) -> list[Node]:
    """Get all nodes matching a query string.

    Args:
        result (KconfigQueryResult): Query results to parse.
        name (str): Name of the item to get.

    Returns:
        list[Node]: List of nodes found.

    """
    if name not in result:
        return []
    return result[name]


def get_single_node(result: KconfigQueryResult, name: str) -> Node:
    """Get a single node from a query result.

    Args:
        result (KconfigQueryResult): Query results to parse.
        name (str): Name of the item to get.

    Raises:
        KconfigQueryImpossibleError: Not exactly one structure (0 or 2+).

    Returns:
        Node: Retrieved node from result.

    """
    nodes = get_nodes(result, name)
    if len(nodes) != 1:
        raise KconfigQueryImpossibleError(f"Impossible: Found {len(nodes)} results: {name}")
    return nodes[0]


def get_single_node_text(result: KconfigQueryResult, name: str) -> str:
    """Get the value of a single node from a query result.

    Args:
        result (KconfigQueryResult): Query results to parse.
        name (str): Name of the item to get.

    Raises:
        KconfigQueryImpossibleError: Missing contents of the structure.

    Returns:
        str: Retrieved item text.

    """
    node = get_single_node(result, name)
    if not node.text:
        raise KconfigQueryImpossibleError(f"Impossible: Missing contents: {name}")
    return node.text.decode("utf-8").strip()


def normalize_field(field: str) -> str:
    """Normalize a field's whitespace.

    Args:
        field (str): Field to normalize.

    Returns:
        str: Normalized field.

    """
    return " ".join(field.split())
