from __future__ import annotations

from .config import CACHE_KERNEL_DIR
from .modules import build_module_struct_cache, get_module_layout
from .structs import build_struct_location_cache, get_struct_location
from .typedefs import build_typedef_location_cache, get_typedef_locations


def build_kernel_cache() -> None:
    """Build kernel-related cache functions."""
    build_struct_location_cache()
    build_typedef_location_cache()


__all__ = [
    "CACHE_KERNEL_DIR",
    "build_kernel_cache",
    "build_module_struct_cache",
    "build_struct_location_cache",
    "get_module_layout",
    "get_struct_location",
    "get_typedef_locations",
]
