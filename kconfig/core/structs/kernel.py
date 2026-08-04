from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.cache import get_struct_location
from kconfig.core.config import kconfig_state
from kconfig.core.parser import dispatch
from kconfig.core.query import run_struct_list
from kconfig.exceptions import KconfigSymbolNotFoundError
from kconfig.types import KconfigParserState
from kconfig.ui import ui

if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigStruct


def find_struct_declaration(struct_name: str) -> tuple[Node, KconfigStruct]:
    """Find the definition of a structure inside the kernel directory."""
    struct_info = get_struct_location(struct_name)
    if struct_info is None:
        raise KconfigSymbolNotFoundError(struct_name, kconfig_state.kernel_dir.name)

    structs = run_struct_list(file=struct_info.file_path)
    goal_struct = [(n, s) for n, s in structs if s.original_name == struct_info.resolved_name]

    if not goal_struct:
        raise KconfigSymbolNotFoundError(struct_name, kconfig_state.kernel_dir.name)
    if len(goal_struct) > 1:
        ui.out_warning(f"{struct_name}: {len(goal_struct)} definitions found, defaulting to first ...")

    return goal_struct[0]


def get_kernel_struct(struct_name: str, recursive: bool) -> KconfigStruct:
    """Get a structure from the kernel."""
    node, layout = find_struct_declaration(struct_name)

    state = KconfigParserState(recursive=recursive)
    dispatch.dispatch(node, state)
    layout.fields = state.fields
    return layout
