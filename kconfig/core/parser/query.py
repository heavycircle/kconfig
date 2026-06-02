from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import tree_sitter
import tree_sitter_c

from kconfig.utils import KconfigFileError, KconfigQueryInvalidError, ui


if TYPE_CHECKING:
    from kconfig.utils import KconfigQueryResult


def _normalize_query_name(name: str) -> str:
    """Normalize the name of query files to ensure an .scm suffix."""
    path = Path(name)
    if path.suffix == ".scm":
        return name
    if path.suffix:
        raise ValueError(f"Invalid file extension: {name}")
    return f"{name}.scm"


def get_query(name: str) -> str:
    """Get an SCM query from its file location.

    This method is dependent on the path of THIS fiel. If this file changes
    location, this function no longer works. There is not really another
    way around this.

    Args:
        name (str): Name of the query file.

    Raises:
        KconfigFileError: Cannot find query file.

    Returns:
        str: Text of the query.

    """
    project_root = Path(__file__).parent.parent.parent.parent
    if not project_root.exists():
        raise KconfigFileError("Cannot find project root!")

    check_dir = project_root / "kconfig"
    if not (check_dir.exists() and check_dir.is_dir()):
        raise KconfigFileError("Project root does not appear valid!")

    query_path = check_dir / "queries" / _normalize_query_name(name)
    if not (query_path.exists() and query_path.is_file()):
        raise KconfigFileError(f"Invalid query name: {name}")

    ui.out_debug(f"Found query file: {query_path.name}")
    return query_path.read_text()


def run_query(code: bytes, query: str) -> KconfigQueryResult:
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
        tree = parser.parse(code)
        query_obj = tree_sitter.Query(c_lang, query)
        cursor = tree_sitter.QueryCursor(query_obj)
        return cursor.matches(tree.root_node)
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
    return run_query(file.read_bytes(), query)
