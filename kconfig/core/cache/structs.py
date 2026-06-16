from __future__ import annotations

import pickle
from typing import TYPE_CHECKING

from kconfig.core import config, parser, utils
from kconfig.types import KconfigStruct
from kconfig.ui import ui

from .config import CACHE_STRUCT_DIR

if TYPE_CHECKING:
    from pathlib import Path

STRUCT_CACHE: dict[str, set[Path]] = {}
"""Cached locations of struct definitions."""

ALIAS_CACHE: dict[str, str] = {}
"""Cached locations of alias definitions."""


def cache_struct_locations() -> None:
    """Cache the struct locations of all structs in the kernel."""
    ui.out_info("Warming the struct location cache (this may take a minute) ...")
    STRUCT_CACHE.clear()
    ALIAS_CACHE.clear()

    for path in config.state.kernel_dir.rglob("*.[ch]"):
        contents = path.read_bytes()

        # Capture structures
        for _, captures in parser.run_query("struct-list", contents):
            struct_names = utils.get_capture_text(captures, "struct.name")
            if not struct_names:
                continue

            STRUCT_CACHE.setdefault(struct_names[0].decode(), set()).add(path)

        # Capture aliases
        for _, captures in parser.run_query("alias-list", contents):
            alias_names = utils.get_capture_text(captures, "alias.name")
            alias_targets = utils.get_capture_text(captures, "alias.target")
            if not (alias_names and alias_targets):
                continue

            alias = alias_names[0].decode("utf-8", errors="replace")
            target = alias_targets[0].decode("utf-8", errors="replace")
            ALIAS_CACHE[alias] = target.replace("struct ", "").replace("union ", "").strip()

    # Cache structs
    struct_cache_file = CACHE_STRUCT_DIR / f"cache_struct_{config.state.kernel_dir.name.replace('.', '_')}.pkl"
    with struct_cache_file.open("wb") as f:
        pickle.dump(STRUCT_CACHE, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Cache aliases
    alias_cache_file = CACHE_STRUCT_DIR / f"cache_alias_{config.state.kernel_dir.name.replace('.', '_')}.pkl"
    with alias_cache_file.open("wb") as f:
        pickle.dump(ALIAS_CACHE, f, protocol=pickle.HIGHEST_PROTOCOL)

    ui.out_success(f"Cached locations for {len(STRUCT_CACHE)} structs and {len(ALIAS_CACHE)} aliases!")


def build_struct_location_cache() -> None:
    """Load the struct cache from disk, or build it if it's missing/invalid."""
    struct_cache_file = CACHE_STRUCT_DIR / f"cache_struct_{config.state.kernel_dir.name.replace('.', '_')}.pkl"
    alias_cache_file = CACHE_STRUCT_DIR / f"cache_alias_{config.state.kernel_dir.name.replace('.', '_')}.pkl"
    if not (struct_cache_file.exists() and alias_cache_file.exists()):
        cache_struct_locations()
        return

    try:
        with struct_cache_file.open("rb") as f:
            STRUCT_CACHE.clear()
            STRUCT_CACHE.update(pickle.load(f))  # noqa: S301

        with alias_cache_file.open("rb") as f:
            ALIAS_CACHE.clear()
            ALIAS_CACHE.update(pickle.load(f))  # noqa: S301

        ui.out_debug(f"Loaded {len(STRUCT_CACHE)} structs and {len(ALIAS_CACHE)} aliases from disk cache!")
    except (pickle.UnpicklingError, KeyError, TypeError):
        ui.out_warning("Cache file corrupted. Rebuilding ...")
        cache_struct_locations()


def _rank_file(path: Path) -> tuple[int, int, str]:
    """Rank a source file that contains a struct definition.

    Args:
        path (Path): The path to check.

    Returns:
        tuple[int, int, str]: A rank of this file, tiered by its path, then
            the length of the path, then its alphabetic name.

    """
    is_header = path.suffix == ".h"

    top = next((p for p in path.parts if p in ("include", "arch")), None)
    if top == "include" and is_header:
        tier = 0
    elif top == "arch" and is_header:
        tier = 1
    elif is_header:
        tier = 2
    else:
        tier = 3

    return (tier, len(path.parts), path.as_posix())


def get_struct_location(struct_name: str) -> KconfigStruct | None:
    """Finds the definition file for a struct.

    This method relies on build_struct_location_cache being called before
    this method. Otherwise, it will always return None.

    Args:
        struct_name (str): The structure to find.

    Returns:
        KconfigStruct | None: The structure found inside the cache, else None
            if it's not in the cache.

    """
    true_name = ALIAS_CACHE.get(struct_name, struct_name)
    if true_name != struct_name:
        ui.out_debug(f"Resolved alias: {struct_name} -> {true_name}")

    if true_name not in STRUCT_CACHE:
        return None

    locations = list(STRUCT_CACHE[true_name])
    if len(locations) == 1:
        return KconfigStruct(struct_name, true_name, locations[0])

    return KconfigStruct(struct_name, true_name, min(locations, key=_rank_file))
