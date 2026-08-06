from __future__ import annotations

import pickle
from typing import TYPE_CHECKING

from kconfig.core.config import CACHE_STRUCT_DIR, kconfig_state
from kconfig.core.query import run_alias_list, run_struct_list
from kconfig.types import KconfigStruct
from kconfig.ui import ui

if TYPE_CHECKING:
    from pathlib import Path


STRUCT_CACHE: dict[str, set[tuple[Path, int]]] = {}
"""Cached locations of struct definitions."""

ALIAS_CACHE: dict[str, set[tuple[str, Path]]] = {}
"""Cached locations of alias definitions."""


def cache_struct_locations() -> None:
    """Cache the struct locations of all structs in the kernel."""
    ui.out_info("Warming the struct location cache (this may take a minute) ...")
    STRUCT_CACHE.clear()
    ALIAS_CACHE.clear()

    for path in kconfig_state.kernel_dir.rglob("*.[ch]"):
        # Capture structures
        for _, struct in run_struct_list(file=path):
            STRUCT_CACHE.setdefault(struct.original_name, set()).add((struct.file_path, struct.file_line))

        # Capture aliases
        for alias, alias_vals in run_alias_list(path).items():
            ALIAS_CACHE.setdefault(alias, set()).update(alias_vals)

    # Cache structs
    struct_cache_file = CACHE_STRUCT_DIR / f"cache_struct_{kconfig_state.kernel_dir.name.replace('.', '_')}.pkl"
    with struct_cache_file.open("wb") as f:
        pickle.dump(STRUCT_CACHE, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Cache aliases
    alias_cache_file = CACHE_STRUCT_DIR / f"cache_alias_{kconfig_state.kernel_dir.name.replace('.', '_')}.pkl"
    with alias_cache_file.open("wb") as f:
        pickle.dump(ALIAS_CACHE, f, protocol=pickle.HIGHEST_PROTOCOL)

    ui.out_success(f"Cached locations for {len(STRUCT_CACHE)} structs and {len(ALIAS_CACHE)} aliases!")


def build_struct_location_cache() -> None:
    """Load the struct cache from disk, or build it if it's missing/invalid."""
    struct_cache_file = CACHE_STRUCT_DIR / f"cache_struct_{kconfig_state.kernel_dir.name.replace('.', '_')}.pkl"
    alias_cache_file = CACHE_STRUCT_DIR / f"cache_alias_{kconfig_state.kernel_dir.name.replace('.', '_')}.pkl"
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


def _rank_file(path: tuple[Path, int]) -> tuple[int, int, int, int, str]:
    """Rank a source file that contains a struct definition.

    Args:
        path (tuple[Path, int]): The (path, line number) to check.

    Returns:
        tuple[int, int, int, int, str]: A rank of this file, tiered by its
            path, whether it's the wrong architecture, location in its path,
            the length of the path, then its name.

    """
    file, line = path
    is_header = file.suffix == ".h"

    # Relative to the kernel root, not just "does 'include' appear anywhere in
    # the path" -- otherwise e.g. tools/include/linux/types.h (a userspace-tool
    # mirror header) ties with the real include/linux/types.h.
    try:
        parts = file.relative_to(kconfig_state.kernel_dir).parts
    except ValueError:
        parts = ()
    top = parts[0] if parts else None

    if top == "include" and is_header:
        tier = 0
    elif top == "arch" and is_header:
        tier = 1
    elif is_header:
        tier = 2
    else:
        tier = 3

    # Within arch/, every architecture's header defines the same struct name
    # (e.g. thread_info) at its own, unrelated line number -- without this,
    # a non-matching architecture could win purely because its definition
    # happens to start earlier in its own file, which is not a real signal.
    wrong_arch = int(tier == 1 and (len(parts) < 2 or parts[1] != kconfig_state.arch))

    return (tier, wrong_arch, line, len(file.parts), file.as_posix())


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
    # Choose struct definitions over aliases.
    if struct_name in STRUCT_CACHE:
        file_path, file_line = min(STRUCT_CACHE[struct_name], key=_rank_file)
        return KconfigStruct(struct_name, file_path, file_line)

    if struct_name in ALIAS_CACHE:
        # Find all aliases, ranking definitions via _rank_file.
        resolutions: list[tuple[str, tuple[Path, int]]] = []
        for alias_name, _ in ALIAS_CACHE[struct_name]:
            if alias_name in STRUCT_CACHE:
                best_path = min(STRUCT_CACHE[alias_name], key=_rank_file)
                resolutions.append((alias_name, best_path))

        if not resolutions:
            return None

        # Rank the aliases using _rank_file.
        best_name, best_path = min(resolutions, key=lambda r: _rank_file(r[1]))
        return KconfigStruct(struct_name, best_path[0], best_path[1], resolved_name=best_name)

    return None
