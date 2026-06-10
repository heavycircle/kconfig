from __future__ import annotations

from kconfig.core import utils
from kconfig.core.config import state
from kconfig.types import KconfigFieldType
from kconfig.ui import ui

from .query import run_query


def get_symbol_typedef(type_name: str) -> KconfigFieldType | None:
    """Find a typedef for a symbol name inside the kernel.

    If this method resolves a struct/union, it returns the entire object. To
    fix this issue would require recursive resolution, which may prove annoying
    with anonymous structures and unions.

    TODO: Implement caching. This method slows down the process immensely.
    """
    for file in utils.find_candidate_struct_files(state.kernel_dir, type_name):
        contents = file.read_bytes()
        for _, captures in run_query("typedef-find", contents):
            typedef_name = utils.get_capture_text(captures, "typedef.name")
            if not typedef_name:
                continue

            found_name = typedef_name[0].decode()
            if found_name == type_name:
                true_name = utils.get_capture_text(captures, "typedef.type")[0].decode()
                ui.out_debug(f"Resolved alias: {type_name} -> {true_name}")
                return KconfigFieldType(type_name, true_name)

    return None
