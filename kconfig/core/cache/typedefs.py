from __future__ import annotations

import pickle
import re
from typing import TYPE_CHECKING

from kconfig.core.config import CACHE_STRUCT_DIR, kconfig_state
from kconfig.core.query import run_query
from kconfig.ui import ui

if TYPE_CHECKING:
    from pathlib import Path

TYPEDEF_CACHE: dict[str, set[Path]] = {}
"""Cached locations of typedefs."""

# A real macro-style typedef's value is just another bare identifier (e.g.
# `#define Elf_Sym Elf64_Sym`). `preproc_arg` captures the *entire* macro body
# verbatim, so without this filter every #define in the tree -- numeric
# constants, flags, function-like macro bodies, ... -- would be cached as a
# "typedef" too (real typedefs, i.e. `type_definition` nodes, aren't affected).
_BARE_IDENTIFIER = re.compile(r"[A-Za-z_]\w*\Z")


def cache_typedef_locations() -> None:
    """Cache the typedef locations of all structs in the kernel."""
    ui.out_info("Warming the typedef location cache (this may take a minute) ...")
    TYPEDEF_CACHE.clear()

    for path in kconfig_state.kernel_dir.rglob("*.[ch]"):
        contents = path.read_bytes()

        for _, captures in run_query("typedef-list", contents):
            if "typedef.name" not in captures:
                continue

            typedef_name = captures["typedef.name"][0]
            if not typedef_name.text:
                continue

            if typedef_name.parent is not None and typedef_name.parent.type == "preproc_def":
                type_node = captures.get("typedef.type", [None])[0]
                type_text = type_node.text.decode(errors="replace") if type_node and type_node.text else ""
                if not _BARE_IDENTIFIER.match(type_text):
                    continue

            TYPEDEF_CACHE.setdefault(typedef_name.text.decode(), set()).add(path)

    # Cache structs
    typedef_cache_file = CACHE_STRUCT_DIR / f"cache_typedef_{kconfig_state.kernel_dir.name.replace('.', '_')}.pkl"
    with typedef_cache_file.open("wb") as f:
        pickle.dump(TYPEDEF_CACHE, f, protocol=pickle.HIGHEST_PROTOCOL)

    ui.out_success(f"Cached locations for {len(TYPEDEF_CACHE)} typedefs!")


def build_typedef_location_cache() -> None:
    """Load the typedef cache from disk, or build it if it's missing/invalid."""
    typedef_cache_file = CACHE_STRUCT_DIR / f"cache_typedef_{kconfig_state.kernel_dir.name.replace('.', '_')}.pkl"
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
