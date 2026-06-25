from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, overload

from kconfig.exceptions import KconfigASTAnomalyError
from kconfig.types import KconfigStruct

from .query import run_query

if TYPE_CHECKING:
    from tree_sitter import Node


PAHOLE_PATTERN = re.compile(r"/\*\s*<\w+>\s*(.+?):(\d+)\s*\*/")


@overload
def run_struct_list(*, code: bytes) -> list[tuple[Node, KconfigStruct]]: ...
@overload
def run_struct_list(*, file: Path) -> list[tuple[Node, KconfigStruct]]: ...


def run_struct_list(*, code: bytes | None = None, file: Path | None = None) -> list[tuple[Node, KconfigStruct]]:
    """Run the ``struct-list`` query to get the list of structures in the snippet.

    If ``code`` is passed instead of ``file``, this method assumes that ``code``
    comes from ``pahole``, so it attempts to parse the line above the struct
    definition for its defining file and line number.

    Args:
        code (bytes): The code to parse.
        file (Path): The path to parse.

    Raises:
        ValueError: Incorrect arguments (neither or both).
        KconfigASTAnomalyError: Missing ``pahole`` definition file/line.

    Returns:
        list[KconfigStruct]: List of structures found in this code.

    """
    if code is None and file is None:
        raise ValueError("Must provide either 'code' or 'file'.")
    if code is not None and file is not None:
        raise ValueError("Provide either 'code' or 'file', not both.")

    body = code or file.read_bytes()
    structs: list[tuple[Node, KconfigStruct]] = []
    for _, captures in run_query("struct-list", body):
        if "struct.name" not in captures:
            continue

        struct_name = captures["struct.name"][0]
        struct_def = captures["struct.def"][0]

        if file is not None:
            file_path = file
            file_line = struct_def.start_point[0] + 1
        else:
            def_line = body.splitlines()[struct_def.start_point[0] - 1].decode()
            match = PAHOLE_PATTERN.search(def_line)
            if not match:
                raise KconfigASTAnomalyError(def_line, "Cannot parse for definition line")

            file_path = Path(match.group(1))
            file_line = int(match.group(2))

        structs.append((struct_def, KconfigStruct(struct_name.text.decode(), file_path, file_line)))

    return structs
