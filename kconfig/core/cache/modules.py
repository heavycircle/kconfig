from __future__ import annotations

import itertools
import pickle
import subprocess
from typing import TYPE_CHECKING

from kconfig.core import parser, utils
from kconfig.core.config import CACHE_MODULE_DIR
from kconfig.exceptions import KconfigSubprocessFailedError
from kconfig.ui import ui

if TYPE_CHECKING:
    from kconfig.types import KconfigStructField


MODULE_CACHE: dict[str, dict[str, list[KconfigStructField]]] = {}
"""Cache containing module capabilities."""


def cache_module_structs() -> None:
    """Build the struct layout cache for a compiled kernel module via ``pahole``.

    Returns:
        dict[str, KconfigStructFields]: Mapping of struct name to its field-to-type map.

    """
    ui.out_info("Warming the module capability cache (this may take a minute) ...")
    MODULE_CACHE.clear()

    ko_files = kconfig_state.module_dir.rglob("*.ko")
    vmlinux_files = list(kconfig_state.module_dir.rglob("vmlinux"))
    target_files = list(itertools.chain(ko_files, vmlinux_files))
    if not target_files:
        ui.out_warning(f"No .ko files found in {kconfig_state.module_dir}")
        return

    for file in target_files:
        cmd = ["pahole", str(file)]

        result = subprocess.run(cmd, check=False, capture_output=True)  # noqa: S603
        if result.returncode != 0 or not result.stdout.strip():
            raise KconfigSubprocessFailedError("pahole", result.stderr.decode().strip())

        for _, captures in parser.run_query("struct-list", result.stdout):
            name_node = utils.get_capture_text(captures, "struct.name")
            if not name_node:
                continue

            name = name_node[0].decode("utf-8", errors="replace")
            fields = parser.parse_struct_specifier(captures["struct.name"][0].parent, file, recursive=False)
            MODULE_CACHE.setdefault(file.as_posix(), {})[name] = fields

    module_cache_file = CACHE_MODULE_DIR / f"cache_module_{kconfig_state.kernel_dir.name.replace('.', '_')}.pkl"
    with module_cache_file.open("wb") as f:
        pickle.dump(MODULE_CACHE, f, protocol=pickle.HIGHEST_PROTOCOL)

    ui.out_success(f"Cached capabilities for {len(target_files)} modules!")


def build_module_struct_cache() -> None:
    """Load the typedef cache from disk, or build it if it's missing/invalid."""
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


def get_module_layout(struct_name: str) -> list[KconfigStructField] | None:
    """Get the modules contained inside the structure."""
    for module in MODULE_CACHE:
        layout = MODULE_CACHE.get(module, {})
        if struct_name in layout:
            return layout[struct_name]

    return None
