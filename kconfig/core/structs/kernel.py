from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import cache, config, parser, utils
from kconfig.exceptions import KconfigSymbolNotFoundError
from kconfig.ui import ui

if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigStruct


def find_struct_declaration(struct_name: str) -> tuple[Node, KconfigStruct]:
    """Find the declaration of a structure inside the kernel directory.

    Args:
        kernel_root (Path): The kernel root to search for.
        struct_name (str): Name of the structure to find.

    Raises:
        KconfigSymbolNotFoundError: Struct not found in any candidate file.

    Returns:
        tuple[Node, KconfigStruct]: The struct's AST node and basic structure information.

    """
    struct_info = cache.get_struct_location(struct_name)
    if not struct_info:
        raise KconfigSymbolNotFoundError(struct_name, config.state.kernel_dir.name)

    contents = struct_info.file.read_bytes()
    for _, captures in parser.run_query("struct-list", contents):
        struct_names = utils.get_capture_text(captures, "struct.name")
        if not struct_names:
            continue

        found_name = struct_names[0].decode()
        if found_name == struct_info.resolved_name:
            rel_file = struct_info.file.relative_to(config.state.kernel_dir)
            struct_info.file = rel_file

            ui.out_debug(f"Found struct '{struct_name}' in {rel_file} ...")
            return captures["struct.name"][0].parent, struct_info

    raise KconfigSymbolNotFoundError(struct_name, config.state.kernel_dir.name)
