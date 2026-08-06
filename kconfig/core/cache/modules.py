from __future__ import annotations

import hashlib
import itertools
import pickle
import subprocess
from typing import TYPE_CHECKING

from kconfig.core.config import CACHE_MODULE_DIR, kconfig_state
from kconfig.core.query import run_struct_list
from kconfig.exceptions import KconfigSubprocessFailedError
from kconfig.ui import ui

if TYPE_CHECKING:
    from pathlib import Path

MODULE_CACHE: dict[str, Path] = {}
"""Cache containing module definition locations."""


def get_pahole_file(file: Path) -> Path:
    """Get the stored pahole file for a given kernel module."""
    file_hash = hashlib.sha256(str(file).replace("/", "_").encode()).hexdigest()
    return CACHE_MODULE_DIR / f"{file.stem}_{file_hash}.h"


def cache_module_structs() -> None:
    """Build the module struct cache for a compiled kernel module via ``pahole``."""
    ui.out_info("Warming the module capability cache (this may take a minute) ...")
    MODULE_CACHE.clear()

    ko_files = kconfig_state.module_dir.rglob("*.ko")
    vmlinux_files = list(kconfig_state.module_dir.rglob("vmlinux"))
    target_files = list(itertools.chain(ko_files, vmlinux_files))
    if not target_files:
        ui.out_warning(f"No .ko files found in {kconfig_state.module_dir}")
        return

    for file in target_files:
        cmd = ["pahole", "-I", str(file)]

        result = subprocess.run(cmd, check=False, capture_output=True)  # noqa: S603
        if result.returncode != 0 or not result.stdout.strip():
            raise KconfigSubprocessFailedError("pahole", result.stderr.decode().strip())

        # Save the pahole output
        pahole_file = get_pahole_file(file)
        with pahole_file.open("wb") as f:
            f.write(result.stdout)

        # Store the pahole dump, not the binary -- that's what struct lookups
        # actually parse back later (see core/structs/module.py).
        for _, struct in run_struct_list(code=result.stdout):
            MODULE_CACHE[struct.original_name] = pahole_file

    module_cache_file = CACHE_MODULE_DIR / f"cache_module_{kconfig_state.kernel_dir.name.replace('.', '_')}.pkl"
    with module_cache_file.open("wb") as f:
        pickle.dump(MODULE_CACHE, f, protocol=pickle.HIGHEST_PROTOCOL)

    ui.out_success(f"Cached capabilities for {len(target_files)} modules!")


def build_module_location_cache() -> None:
    """Load the module cache from disk, or build it if it's missing/invalid."""
    module_cache_file = CACHE_MODULE_DIR / f"cache_module_{kconfig_state.kernel_dir.name.replace('.', '_')}.pkl"
    if not module_cache_file.exists():
        cache_module_structs()
        return

    try:
        with module_cache_file.open("rb") as f:
            MODULE_CACHE.clear()
            MODULE_CACHE.update(pickle.load(f))  # noqa: S301

        ui.out_debug(f"Loaded {len(MODULE_CACHE)} modules from disk cache.")
    except (pickle.UnpicklingError, KeyError, TypeError):
        ui.out_warning("Cache file corrupted. Rebuilding ...")
        cache_module_structs()


def get_module_location(struct_name: str) -> Path | None:
    """Get the location of a struct definition in our modules."""
    return MODULE_CACHE.get(struct_name)
