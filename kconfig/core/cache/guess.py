from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.query.struct_list import run_struct_list
from kconfig.core.utils import dispatcher
from kconfig.types import KconfigParserState, KconfigStruct

if TYPE_CHECKING:
    from pathlib import Path


def get_file_structs(file: Path) -> list[KconfigStruct]:
    """Get the structs inside a file.

    Args:
            file (Path): The file to parse.

    Returns:
            list[KconfigStruct]: The list of structures inside the file.

    """
    structs: list[KconfigStruct] = []
    for node, struct in run_struct_list(file=file):
        state = KconfigParserState()
        dispatcher.dispatch(node, state)

        struct.fields = state.fields
        structs.append(struct)

    return structs
