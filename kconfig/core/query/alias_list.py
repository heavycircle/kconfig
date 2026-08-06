from __future__ import annotations

from typing import TYPE_CHECKING

from .query import run_query

if TYPE_CHECKING:
    from pathlib import Path


def run_alias_list(file: Path) -> dict[str, set[tuple[str, Path]]]:
    """Run the ``alias-list`` query to get the list of structures in the snippet.

    Args:
        file (Path): The path to parse.

    Raises:
        ValueError: Incorrect arguments (neither or both).
        KconfigASTAnomalyError: Missing ``pahole`` definition file/line.

    Returns:
        dict[str, set[tuple[str, Path]]]: Dictionary connecting alias names
            to a set of (value, file) they are typedef'ed to.

    """
    alias_dict: dict[str, set[tuple[str, Path]]] = {}
    for _, captures in run_query("alias-list", file.read_bytes()):
        if "alias.name" not in captures:
            continue

        name_node = captures["alias.name"][0]
        target_node = captures["alias.target"][0]
        if not name_node.text or not target_node.text:
            continue

        alias_key = name_node.text.decode(errors="replace")
        alias_val = target_node.text.decode(errors="replace")

        alias_dict.setdefault(alias_key, set()).add((alias_val, file))

    return alias_dict
