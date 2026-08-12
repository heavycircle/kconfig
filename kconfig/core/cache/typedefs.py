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

NON_KERNEL_BINARY_DIRS = frozenset({"scripts", "tools", "Documentation", "usr"})
"""Top-level kernel-tree directories that are never compiled into the kernel
binary or a module -- host-side build tooling, userspace utilities, and
documentation. `resolve_typedef` ORs together the guard from *every* location
a typedef name is defined, so a same-named macro here (confirmed via
`Elf_Sym`, redefined independently for their own unrelated purposes by
`scripts/mod/modpost.h`, `scripts/sorttable.h`, `scripts/recordmcount.h`,
`tools/perf/util/genelf.h`, and `scripts/insert-sys-cert.c`) inflates the
resulting guard with terms that have nothing to do with the guard under which
a *compiled* struct's typedef actually resolves -- most of those aren't even
real CONFIG symbols (e.g. `RECORD_MCOUNT_64`, a host-tool compile-mode
macro)."""


def _is_kernel_binary_path(path: Path) -> bool:
    """Whether ``path`` could plausibly end up compiled into the kernel or a module."""
    try:
        parts = path.relative_to(kconfig_state.kernel_dir).parts
    except ValueError:
        return True

    return not parts or parts[0] not in NON_KERNEL_BINARY_DIRS


def _matches_target_arch(path: Path) -> bool:
    """Whether ``path`` isn't a different architecture's ``arch/<arch>/...`` file.

    Mirrors ``core/cache/structs.py::_rank_file``'s ``wrong_arch`` check --
    every architecture defines its own version of common typedefs, so without
    this an unrelated architecture's guard gets ORed in alongside the target
    one. Checked dynamically (not baked into the on-disk cache) so it tracks
    ``kconfig_state.arch`` even when it changes within the same process.
    """
    try:
        parts = path.relative_to(kconfig_state.kernel_dir).parts
    except ValueError:
        return True

    return len(parts) < 2 or parts[0] != "arch" or parts[1] == kconfig_state.arch


def cache_typedef_locations() -> None:
    """Cache the typedef locations of all structs in the kernel."""
    ui.out_info("Warming the typedef location cache (this may take a minute) ...")
    TYPEDEF_CACHE.clear()

    for path in kconfig_state.kernel_dir.rglob("*.[ch]"):
        if not _is_kernel_binary_path(path):
            continue

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
    return [path for path in TYPEDEF_CACHE.get(typedef_name, set()) if _matches_target_arch(path)]
