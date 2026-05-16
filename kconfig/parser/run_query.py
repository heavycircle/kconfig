from __future__ import annotations

from typing import TYPE_CHECKING

import tree_sitter
import tree_sitter_c


if TYPE_CHECKING:
    from pathlib import Path


def run_query(c_file: Path, query: str) -> dict[str, list[tree_sitter.Node]]:
    """Run a tree-sitter query on a C file.

    Args:
        c_file (Path): Path to the C file to query.
        query_str (str): Tree-sitter (SCM) query..

    Returns:
        dict[str, list[Node]]: Resulting structure of the query.

    Raises:
        ValueError: Missing c_file or missing query_file.

    """
    if not c_file.exists():
        raise ValueError(f"No such file or directory: {c_file.name}")

    c_lang = tree_sitter.Language(tree_sitter_c.language())
    parser = tree_sitter.Parser(c_lang)

    # Build AST from C file
    file_bytes = c_file.read_bytes()
    tree = parser.parse(file_bytes)

    # Query AST
    query_obj = tree_sitter.Query(c_lang, query)
    cursor = tree_sitter.QueryCursor(query_obj)
    return cursor.captures(tree.root_node)
