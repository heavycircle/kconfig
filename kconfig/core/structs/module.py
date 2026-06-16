from __future__ import annotations

from kconfig.core import cache, config
from kconfig.exceptions import KconfigSymbolNotFoundError


def get_module_struct(struct_name: str) -> dict[str, str]:
    """Get a struct's source from a kernel module.

    Args:
        struct_name (str): Name of the structure.

    Returns:
        dict[str, str]: Field-to-type mapping for the requested structure.

    """
    layout = cache.get_module_layout(struct_name)
    if not layout:
        raise KconfigSymbolNotFoundError(struct_name, config.state.module_dir)

    return {field.field_name: field.field_type.original_type for field in layout}
