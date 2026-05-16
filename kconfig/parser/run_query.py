from __future__ import annotations

from typing import TYPE_CHECKING

import tree_sitter
import tree_sitter_c


if TYPE_CHECKING:
    from pathlib import Path


def run_query(code: str, query: str) -> dict[str, list[tree_sitter.Node]]:
    """Run a tree-sitter query on C code.

    Args:
        code (str): Code to query.
        query (str): Tree-sitter (SCM) query.

    Returns:
        dict[str, list[Node]]: Resulting structure of the query.

    """
    c_lang = tree_sitter.Language(tree_sitter_c.language())
    parser = tree_sitter.Parser(c_lang)

    file_bytes = code.encode("utf-8")
    tree = parser.parse(file_bytes)

    query_obj = tree_sitter.Query(c_lang, query)
    cursor = tree_sitter.QueryCursor(query_obj)
    return cursor.captures(tree.root_node)


def run_file_query(file: Path, query: str) -> dict[str, list[tree_sitter.Node]]:
    """Run a tree-sitter query on a C file.

    Args:
        file (Path): Path to the C file to query.
        query (str): Tree-sitter (SCM) query..

    Returns:
        dict[str, list[Node]]: Resulting structure of the query.

    Raises:
        ValueError: Missing c_file or missing query_file.

    """
    if not file.exists():
        raise ValueError(f"No such file or directory: {file.name}")

    return run_query(file.read_text(), query)
