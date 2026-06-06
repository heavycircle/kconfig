from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import tree_sitter
import tree_sitter_c

from kconfig.utils import (
    KconfigFileInvalidError,
    KconfigFileNotFoundError,
    KconfigQueryCapture,
    KconfigQuerySyntaxError,
)


if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.utils import KconfigQueryResult


TS_LANG = tree_sitter.Language(tree_sitter_c.language())
TS_PARSER = tree_sitter.Parser(TS_LANG)
TS_CACHE: dict[str, tree_sitter.Query] = {}


def _normalize_query_name(name: str) -> str:
    """Normalize the name of query files to ensure an .scm suffix."""
    path = Path(name)
    if path.suffix == ".scm":
        return name
    if path.suffix:
        raise KconfigFileInvalidError(name, "Invalid file extension")
    return f"{name}.scm"


def get_query(name: str) -> tree_sitter.Query:
    """Compile an SCM query from its file location.

    If this query has been compiled before, it returns from the cache.

    Args:
        name (str): Name of the query file.

    Raises:
        KconfigFileNotFoundError: Cannot find query file.
        KconfigQuerySyntaxError: Invalid SCM syntax.

    Returns:
        Query: Compiled query object.

    """
    if name in TS_CACHE:
        return TS_CACHE[name]

    project_root = Path(__file__).parent.parent.parent.parent
    if not project_root.exists():
        raise KconfigFileNotFoundError(project_root)

    query_path = project_root / "kconfig" / "queries" / _normalize_query_name(name)
    if not (query_path.exists() and query_path.is_file()):
        raise KconfigFileNotFoundError(query_path)

    try:
        query_str = query_path.read_text()
        query = tree_sitter.Query(TS_LANG, query_str)

        TS_CACHE[name] = query
        return query
    except tree_sitter.QueryError as e:
        raise KconfigQuerySyntaxError(str(e)) from e


def run_query(query: str, code: bytes) -> KconfigQueryResult:
    """Run a tree-sitter query on C code.

    Args:
        query (str): Tree-sitter (SCM) query name (without ``.scm`` extension).
        code (bytes): C source code to query.

    Returns:
        KconfigQueryResult: Resulting structure of the query.

    """
    tree = TS_PARSER.parse(code)
    cursor = tree_sitter.QueryCursor(get_query(query))
    return cursor.matches(tree.root_node)


def run_node_query(node: Node, query: str) -> KconfigQueryCapture:
    """Run a cached query against a pre-parsed AST node.

    Args:
        node (Node): Pre-parsed AST node to run the query against.
        query (str): Tree-sitter (SCM) query name (without ``.scm`` extension).

    Raises:
        KconfigFileNotFoundError: Query file does not exist.
        KconfigQuerySyntaxError: Query file contains invalid SCM syntax.

    Returns:
        KconfigQueryCapture: Flattened capture dict mapping capture names to node lists.

    """
    cursor = tree_sitter.QueryCursor(get_query(query))
    captures = cursor.matches(node)

    result: KconfigQueryCapture = {}
    for _, matches in captures:
        for name, nodes in matches.items():
            result.setdefault(name, []).extend(nodes)

    return result
