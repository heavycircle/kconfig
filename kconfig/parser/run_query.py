from pathlib import Path

import tree_sitter
import tree_sitter_c


def run_query(c_file: Path, query_file: Path) -> None:
    """Run a tree-sitter query on a C file.

    Args:
        c_file (Path): Path to the C file to query.
        query_file (Path): Path to the query (.scm) file.

    Raises:
        ValueError: Missing c_file or missing query_file.

    Returns:
        dict: Dictionary of matching queries.
    """
    if not c_file.exists():
        raise ValueError(f"No such file or directory: {c_file.name}")
    if not query_file.exists():
        raise ValueError(f"No such file or directory: {query_file.name}")

    c_lang = tree_sitter.Language(tree_sitter_c.language())
    parser = tree_sitter.Parser(c_lang)

    # Build AST from C file
    file_bytes = c_file.read_bytes()
    tree = parser.parse(file_bytes)

    query_str = query_file.read_text()
    query = tree_sitter.Query(c_lang, query_str)

    cursor = tree_sitter.QueryCursor(query)
    captures = cursor.captures(tree.root_node)
    for name, nodes in captures.items():
        for node in nodes:
            text = node.text.decode("utf-8").strip()

            start = node.start_point[0] + 1
            end = node.end_point[0] + 1

            print(f"[{start}:{end}] {name}:")
            print(text, end="\n\n")

    return
