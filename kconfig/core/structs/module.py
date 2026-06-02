from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from kconfig.utils import KconfigFileInvalidError, KconfigStruct


if TYPE_CHECKING:
    from pathlib import Path


def get_module_struct(ko_path: Path, struct_name: str) -> KconfigStruct:
    """Get a struct's source from a kernel module.

    Args:
        ko_path (Path): Path to the kernel module.
        struct_name (str): Name of the structure.

    Returns:
        list[str]: Items found in the structure.

    """
    cmd = ["pahole", "-C", struct_name, "-E", str(ko_path)]

    result = subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
    if result.returncode != 0 or not result.stdout.strip():
        raise KconfigFileInvalidError(f"Failed to find struct: {ko_path}")

    return KconfigStruct(name=struct_name, body=result.stdout, file=ko_path)
