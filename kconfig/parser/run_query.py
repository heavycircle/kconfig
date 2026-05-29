from __future__ import annotations

from typing import TYPE_CHECKING

import tree_sitter
import tree_sitter_c

from kconfig.utils import KconfigFileError, KconfigQueryInvalidError


if TYPE_CHECKING:
    from pathlib import Path

    from kconfig.utils import KconfigQueryResult


def run_query(code: str, query: str) -> KconfigQueryResult:
    """Run a tree-sitter query on C code.

    Args:
        code (str): Code to query.
        query (str): Tree-sitter (SCM) query.

    Raises:
        KconfigQueryInvalidError: Invalid formatted SCM query.

    Returns:
        KconfigQueryResult: Resulting structure of the query.

    """
    c_lang = tree_sitter.Language(tree_sitter_c.language())
    parser = tree_sitter.Parser(c_lang)

    try:
        tree = parser.parse(code.encode("utf-8"))
        query_obj = tree_sitter.Query(c_lang, query)
        cursor = tree_sitter.QueryCursor(query_obj)
        return cursor.captures(tree.root_node)
    except tree_sitter.QueryError as e:
        raise KconfigQueryInvalidError(f"Invalid Query: {e}") from e


def run_file_query(file: Path, query: str) -> KconfigQueryResult:
    """Run a tree-sitter query on a C file.

    Args:
        file (Path): Path to the C file to query.
        query (str): Tree-sitter (SCM) query.

    Raises:
        KconfigFileError: Missing C or SCM file.

    Returns:
        KconfigQueryResult: Resulting structure of the query.

    """
    if not (file.exists() or file.is_file()):
        raise KconfigFileError(f"No such file or directory: {file.name}")
    return run_query(file.read_text(), query)
