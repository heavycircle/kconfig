from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.cache import get_module_location
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
    """Find the definition of a module structure."""
    struct_file = get_module_location(struct_name)
    if struct_file is None:
        raise KconfigSymbolNotFoundError(struct_name, kconfig_state.kernel_dir.name)

    structs = run_struct_list(code=struct_file.read_bytes())
    goal_struct = [(n, s) for n, s in structs if s.original_name == struct_name]

    if not goal_struct:
        raise KconfigSymbolNotFoundError(struct_name, kconfig_state.kernel_dir.name)
    if len(goal_struct) > 1:
        ui.out_warning(f"{struct_name}: {len(goal_struct)} definitions found, defaulting to first ...")

    return goal_struct[0]


def get_module_struct(struct_name: str) -> KconfigStruct:
    """Get a structure from the kernel."""
    node, layout = find_struct_declaration(struct_name)

    state = KconfigParserState(recursive=False)
    dispatch.dispatch(node, state)
    layout.fields = state.fields
    return layout
