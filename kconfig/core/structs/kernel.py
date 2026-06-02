from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser, utils
from kconfig.utils import KconfigFileNoMatchError, KconfigStruct, ui

from .utils import get_struct_configs


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
        result = parser.run_query(contents, query)
        if not result:
            continue

        ui.out_debug(f"Found struct {struct_name} in {file} ...")
        return KconfigStruct(
            name=utils.get_single_node_text(result, "struct.name").decode(),
            body=utils.get_single_node_text(result, "struct.def"),
            file=file,
        )

    raise KconfigFileNoMatchError(f"Cannot find a file defining: {struct_name}")


def get_kernel_struct(kernel_root: Path, struct_name: str) -> KconfigStruct:
    """Get a structure's configuration from the kernel.

    Args:
        kernel_root (Path): The kernel root to search for.
        struct_name (str): Name of the structure to find.

    Returns:
        KconfigStruct: Structure information, to include configuration options.

    """
    struct = get_kernel_struct_code(kernel_root, struct_name)
    return get_struct_configs(struct)
