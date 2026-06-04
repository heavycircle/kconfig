from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser, utils
from kconfig.utils import (
    KconfigFileNoMatchError,
    KconfigQueryNoMatchError,
    KconfigStruct,
    KconfigSymbolAliasedError,
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
    # BUG: This fails to find 'if defined(CONFIG_)'. Example: rpc_xprt
    query = parser.get_query("struct-find").replace("__STRUCT_NAME__", struct_name)
    for file in utils.find_candidate_struct_files(kernel_root, struct_name):
        contents = file.read_bytes()
        for _, captures in parser.run_query(contents, query):
            struct_names = utils.get_capture_text(captures, "struct.name")
            struct_defs = utils.get_capture_text(captures, "struct.def")
            if not (struct_names and struct_defs):
                continue

            ui.out_debug(f"Found struct {struct_name} in {file} ...")
            return KconfigStruct(
                name=struct_names[0].decode(),
                body=struct_defs[0],
                file=file,
            )

    true_name = get_kernel_struct_alias(kernel_root, struct_name)
    if true_name:
        raise KconfigSymbolAliasedError(original_name=struct_name, true_name=true_name)
    raise KconfigFileNoMatchError(f"Cannot find a file defining: {struct_name}")


def get_recursive_kernel_struct(
    kernel_root: Path, struct_name: str, visited: set[str] | None = None
) -> KconfigStruct | None:
    """Recursively find nested structures inside a given structure."""
    if visited is None:
        visited = set()
    if struct_name in visited:
        return None
    visited.add(struct_name)

    struct = get_kernel_struct(kernel_root, struct_name)
    members = get_custom_struct_members(struct.body)
    for member in members.structs:
        ui.out_debug(f" >> {struct_name} has recursive member: {member}")
        nested_struct = get_recursive_kernel_struct(kernel_root, member, visited)
        if nested_struct:
            struct.nested_structs.append(nested_struct)

    return struct


def get_kernel_struct(kernel_root: Path, struct_name: str, recursive: bool = False) -> KconfigStruct:
    """Get a structure's configuration from the kernel.

    Args:
        kernel_root (Path): The kernel root to search for.
        struct_name (str): Name of the structure to find.
        recursive (bool): True to search for recursive definitions.
            Can be intense, so defaults to False.

    Returns:
        KconfigStruct: Structure information, to include configuration options.

    """
    if recursive:
        ui.out_info(f"Checking recursively: {struct_name}")
        struct = get_recursive_kernel_struct(kernel_root, struct_name)
        if not struct:
            raise KconfigQueryNoMatchError(f"Could not find struct: {struct_name}")
        return struct

    try:
        struct = get_kernel_struct_code(kernel_root, struct_name)
    except KconfigSymbolAliasedError as e:
        ui.out_debug(f"Found Alias: {e.original_name} -> {e.true_name}")
        struct = get_kernel_struct_code(kernel_root, e.true_name)
        # TODO: Maybe store its original name somewhere.

    return get_struct_configs(struct)
