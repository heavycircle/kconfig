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
    from pathlib import Path

    from tree_sitter import Node

    from kconfig.types import KconfigStruct

MODULE_STRUCT_INDEX: dict[Path, dict[str, list[tuple[Node, KconfigStruct]]]] = {}
"""Cache of every struct parsed out of a pahole dump, keyed by that dump's file.

A single ``vmlinux`` can define tens of thousands of structs, so this is
memoized per file rather than re-parsed on every single struct lookup.
"""


def _index_pahole_file(pahole_file: Path) -> dict[str, list[tuple[Node, KconfigStruct]]]:
    if pahole_file not in MODULE_STRUCT_INDEX:
        index: dict[str, list[tuple[Node, KconfigStruct]]] = {}
        for node, struct in run_struct_list(code=pahole_file.read_bytes()):
            index.setdefault(struct.original_name, []).append((node, struct))

        MODULE_STRUCT_INDEX[pahole_file] = index

    return MODULE_STRUCT_INDEX[pahole_file]


def find_struct_declaration(struct_name: str) -> tuple[Node, KconfigStruct]:
    """Find the definition of a module structure."""
    pahole_file = get_module_location(struct_name)
    if pahole_file is None:
        raise KconfigSymbolNotFoundError(struct_name, kconfig_state.kernel_dir.name)

    matches = _index_pahole_file(pahole_file).get(struct_name, [])
    if not matches:
        raise KconfigSymbolNotFoundError(struct_name, kconfig_state.kernel_dir.name)
    if len(matches) > 1:
        ui.out_warning(f"{struct_name}: {len(matches)} definitions found, defaulting to first ...")

    return matches[0]


def get_module_struct(struct_name: str) -> KconfigStruct:
    """Get a structure from the kernel."""
    node, layout = find_struct_declaration(struct_name)

    state = KconfigParserState(recursive=False)
    dispatch.dispatch(node, state)
    layout.fields = state.fields
    return layout
