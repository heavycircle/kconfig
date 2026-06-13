from __future__ import annotations

import pickle
from typing import TYPE_CHECKING

from kconfig.core import config, parser, utils
from kconfig.ui import ui

from .config import CACHE_STRUCT_DIR


if TYPE_CHECKING:
    from pathlib import Path

TYPEDEF_CACHE: dict[str, set[Path]] = {}
"""Cached locations of typedefs."""


def cache_typedef_locations() -> None:
    """Cache the typedef locations of all structs in the kernel."""
    ui.out_info("Warming the typedef location cache (this may take a minute) ...")
    TYPEDEF_CACHE.clear()

    for path in config.state.kernel_dir.rglob("*.[ch]"):
        contents = path.read_bytes()

        for _, captures in parser.run_query("typedef-list", contents):
            typedef_names = utils.get_capture_text(captures, "typedef.name")
            if not typedef_names:
                continue

            TYPEDEF_CACHE.setdefault(typedef_names[0].decode(), set()).add(path)

    # Cache structs
    typedef_cache_file = CACHE_STRUCT_DIR / f"cache_typedef_{config.state.kernel_dir.name.replace('.', '_')}.pkl"
    with typedef_cache_file.open("wb") as f:
        pickle.dump(TYPEDEF_CACHE, f, protocol=pickle.HIGHEST_PROTOCOL)

    ui.out_success(f"Cached locations for {len(TYPEDEF_CACHE)} typedefs!")


def build_typedef_location_cache() -> None:
    """Load the typedef cache from disk, or build it if it's missing/invalid."""
    typedef_cache_file = CACHE_STRUCT_DIR / f"cache_typedef_{config.state.kernel_dir.name.replace('.', '_')}.pkl"
    if not typedef_cache_file.exists():
        cache_typedef_locations()
        return

    try:
        with typedef_cache_file.open("rb") as f:
            TYPEDEF_CACHE.clear()
            TYPEDEF_CACHE.update(pickle.load(f))  # noqa: S301

        ui.out_debug(f"Loaded {len(TYPEDEF_CACHE)} typedefs from disk cache!")
    except (pickle.UnpicklingError, KeyError, TypeError):
        ui.out_warning("Cache file corrupted. Rebuilding ...")
        cache_typedef_locations()


def get_typedef_locations(typedef_name: str) -> list[Path]:
    """Find the locations a typedef is defined.

    This method returns all files that contain a typedef. This is extremely
    important for determining the configs that yield the correct typedef.
    """
    return list(TYPEDEF_CACHE.get(typedef_name, set()))
