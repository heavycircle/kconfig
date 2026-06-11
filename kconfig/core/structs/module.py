from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import cache, utils
from kconfig.exceptions import KconfigSymbolNotFoundError


if TYPE_CHECKING:
    from pathlib import Path

    from kconfig.types import KconfigStructFields


def get_module_struct(module_root: Path, struct_name: str) -> KconfigStructFields:
    """Get a struct's source from a kernel module.

    Args:
        module_root (Path): Base kernel module directory.
        struct_name (str): Name of the structure.

    Returns:
        KconfigStructFields: Field-to-type mapping for the requested structure.

    """
    for file in utils.find_candidate_kernel_modules(module_root, struct_name):
        layout = cache.get_module_layout(file)
        if struct_name in layout:
            return layout[struct_name]

    raise KconfigSymbolNotFoundError(struct_name, module_root)
