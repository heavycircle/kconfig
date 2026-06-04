from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser, utils
from kconfig.utils import (
    KconfigStruct,
    KconfigSymbolAliasedError,
    KconfigSymbolNotFoundError,
    ui,
)

from .utils import get_custom_struct_members, get_struct_configs


if TYPE_CHECKING:
    from pathlib import Path


def get_kernel_struct_alias(kernel_root: Path, struct_name: str) -> str | None:
    """Hunt for #define or typedef that aliases this symbol."""
    query = parser.get_query("alias-find")
    for file in utils.find_candidate_struct_files(kernel_root, struct_name):
        contents = file.read_bytes()
        for _, captures in parser.run_query(contents, query):
            alias_name = utils.get_capture_text(captures, "alias.name")
            alias_target = utils.get_capture_text(captures, "alias.target")
            if alias_name and alias_name[0].decode() == struct_name:
                return alias_target[0].decode()

    return None


def get_kernel_struct_code(kernel_root: Path, struct_name: str) -> KconfigStruct:
    """Find a structure by name inside a C file.

    Args:
        kernel_root (Path): The kernel root to search for.
        struct_name (str): Name of the structure to find.

    Raises:
        KconfigFileError: Missing C or Query (SCM) file.

    Returns:
        KconfigStruct: Matching structure inside source file.

    """
    query = parser.get_query("struct-find").replace("__STRUCT_NAME__", struct_name)
    for file in utils.find_candidate_struct_files(kernel_root, struct_name):
        contents = file.read_bytes()
        for _, captures in parser.run_query(contents, query):
            struct_names = utils.get_capture_text(captures, "struct.name")
            struct_defs = utils.get_capture_text(captures, "struct.def")
            if not (struct_names and struct_defs):
                continue

            ui.out_debug(f"Found struct {struct_name} in {file} ...")
            return KconfigStruct(name=struct_names[0].decode(), body=struct_defs[0], file=file)

    true_name = get_kernel_struct_alias(kernel_root, struct_name)
    if true_name:
        raise KconfigSymbolAliasedError(original_name=struct_name, true_name=true_name)
    raise KconfigSymbolNotFoundError(struct_name, kernel_root)


def get_kernel_struct(kernel_root: Path, struct_name: str, recursive: bool = False, visited: set[str] | None = None) -> KconfigStruct | None:
    """Get a structure's configuration from the kernel.

    Args:
        kernel_root (Path): The kernel root to search for.
        struct_name (str): Name of the structure to find.
        recursive (bool): True to search for recursive definitions.
            Can be intense, so defaults to False.

    Returns:
        KconfigStruct: Structure information, to include configuration options.

    """
    if visited is None:
        visited = set()
        
    if struct_name in visited:
        ui.out_debug(f"Cycle detected for '{struct_name}', skipping ...")
        return None
    visited.add(struct_name)

    try:
        struct = get_kernel_struct_code(kernel_root, struct_name)
    except KconfigSymbolAliasedError as e:
        ui.out_debug(f"Found Alias: {e.original_name} -> {e.true_name}")
        struct = get_kernel_struct_code(kernel_root, e.true_name)
        # TODO: Maybe store its original name somewhere.

    struct.configs = get_struct_configs(struct)
    
    if recursive:
        ui.out_debug(f" >> Checking recursively: {struct_name}")
        members = get_custom_struct_members(struct.body)
        for member in members.structs:
            ui.out_debug(f" >> {struct_name} has recursive member: {member}")

            try:
                nested_struct = get_kernel_struct(kernel_root, member, recursive=True, visited=visited)
                if nested_struct:
                    struct.nested_structs.append(nested_struct)
            except KconfigSymbolNotFoundError as e:
                ui.out_debug(f"Could not find nested struct: '{member}': {e}")

        return struct
            raise KconfigQueryNoMatchError(f"Could not find struct: {struct_name}")
        return struct
