from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser, utils
from kconfig.utils import KconfigFileNoMatchError, KconfigStruct, ui

from .utils import get_custom_struct_members, get_struct_configs


if TYPE_CHECKING:
    from pathlib import Path


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
    for file in utils.find_candidate_header_files(kernel_root, struct_name):
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

    raise KconfigFileNoMatchError(f"Cannot find a file defining: {struct_name}")


def get_recursive_kernel_struct(kernel_root: Path, struct_name: str, visited: set[str] | None = None) -> KconfigStruct:
    """Recursively find nested structures inside a given structure."""
    if visited is None:
        visited = set()

    if struct_name in visited:
        return None

    visited.add(struct_name)

    struct = get_kernel_struct(kernel_root, struct_name)
    for member in get_custom_struct_members(struct.body):
        print(member)


def get_kernel_struct(kernel_root: Path, struct_name: str, recursive: bool = False) -> KconfigStruct:
    """Get a structure's configuration from the kernel.

    Args:
        kernel_root (Path): The kernel root to search for.
        struct_name (str): Name of the structure to find.

    Returns:
        KconfigStruct: Structure information, to include configuration options.

    """
    if recursive:
        ui.out_info(f"Checking recursively: {struct_name}")
        return get_recursive_kernel_struct(kernel_root, struct_name)

    struct = get_kernel_struct_code(kernel_root, struct_name)
    return get_struct_configs(struct)
