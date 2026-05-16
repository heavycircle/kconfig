from __future__ import annotations

from pathlib import Path

from kconfig.utils.exceptions import KconfigQueryError

from .run_query import run_query


def find_struct(c_file: Path, struct_name: str) -> str:
    """Run a tree-sitter query on a C file.

    Args:
        c_file (Path): Path to the C file to query.
        query_file (Path): Path to the query (.scm) file.

    Raises:
        ValueError: Missing c_file or missing query_file.

    Returns:
        str: Matching structure in source file.

    """
    project_root = Path(__file__).parent.parent
    query_file = project_root / "queries" / "find-struct.scm"
    if not query_file.exists():
        raise RuntimeError(f"Missing query: {query_file}")
    query_text = query_file.read_text()
    query_str = query_text.replace("__STRUCT_NAME__", struct_name)

    result = run_query(c_file, query_str)
    if "struct.def" not in result:
        raise KconfigQueryError(f"Failed to find structure: {struct_name}")
    len_results = len(result["struct.def"])
    if len_results != 1:
        raise KconfigQueryError(f"Impossible: Found {len_results} structures: {struct_name}")

    node = result["struct.def"][0]
    if not node.text:
        raise KconfigQueryError(f"Impossible: Missing contents of structure: {struct_name}")
    return node.text.decode("utf-8").strip()
