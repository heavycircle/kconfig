from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import cache, parser, utils
from kconfig.core.config import state
from kconfig.exceptions import KconfigSymbolNotFoundError
from kconfig.ui import ui


if TYPE_CHECKING:
    from pathlib import Path

    from tree_sitter import Node


def find_struct_declaration(struct_name: str) -> tuple[Node, Path]:
    """Find the declaration of a structure inside the kernel directory.

    Args:
        kernel_root (Path): The kernel root to search for.
        struct_name (str): Name of the structure to find.

    Raises:
        KconfigSymbolNotFoundError: Struct not found in any candidate file.

    Returns:
        tuple[Node, Path]: The struct's AST node and the file it was found in.

    """
    struct_file = cache.get_struct_location(struct_name)
    if not struct_file:
        raise KconfigSymbolNotFoundError(struct_name, state.kernel_dir)

    contents = struct_file.read_bytes()
    for _, captures in parser.run_query("struct-list", contents):
        struct_names = utils.get_capture_text(captures, "struct.name")
        if not struct_names:
            continue

        found_name = struct_names[0].decode()
        if found_name == struct_name:
            rel_file = struct_file.relative_to(state.kernel_dir)
            ui.out_debug(f"Found struct {struct_name} in {rel_file} ...")
            return captures["struct.name"][0].parent, rel_file

    ui.out_debug(f"Cannot find '{struct_name}', searching for aliases ...")
    for file in utils.find_candidate_struct_files(state.kernel_dir, struct_name):
        contents = file.read_bytes()
        for _, captures in parser.run_query("alias-find", contents):
            alias_names = utils.get_capture_text(captures, "alias.name")
            if not alias_names:
                continue

            found_alias = alias_names[0].decode()
            if found_alias == struct_name:
                true_name = utils.get_capture_text(captures, "alias.target")[0].decode()
                ui.out_debug(f"Resolved alias: {struct_name} -> {true_name}")
                return find_struct_declaration(true_name)

    raise KconfigSymbolNotFoundError(struct_name, state.kernel_dir)
