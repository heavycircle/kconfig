from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

from kconfig.core import config, parser, utils
from kconfig.exceptions import KconfigSubprocessFailedError
from kconfig.ui import ui

from .config import CACHE_MODULE_DIR


if TYPE_CHECKING:
    from pathlib import Path

    from kconfig.types import KconfigStructFields


MODULE_CACHE: dict[str, dict] = {}
"""Cache containing module capabilities."""

module_cache_file = CACHE_MODULE_DIR / "module_layouts.json"


def cache_module_structs(ko_path: Path) -> dict[str, KconfigStructFields]:
    """Build the struct layout cache for a compiled kernel module via ``pahole``.

    Args:
        ko_path (Path): Path to the ``.ko`` kernel object file.

    Returns:
        dict[str, KconfigStructFields]: Mapping of struct name to its field-to-type map.

    """
    cmd = ["pahole", str(ko_path)]

    result = subprocess.run(cmd, check=False, capture_output=True)  # noqa: S603
    if result.returncode != 0 or not result.stdout.strip():
        raise KconfigSubprocessFailedError("pahole", result.stderr.decode().strip())

    module_cache: dict[str, KconfigStructFields] = {}
    for _, captures in parser.run_query("struct-list", result.stdout):
        name_node = utils.get_capture_text(captures, "struct.name")
        if not name_node:
            continue

        fields = parser.parse_struct_specifier(captures["struct.name"][0].parent, ko_path, recursive=False)
        mapping = {f.field_name: f.field_type.original_type for f in fields}
        module_cache[name_node[0].decode("utf-8", errors="replace")] = mapping

    return module_cache


def get_module_layout(ko_path: Path) -> dict[str, KconfigStructFields]:
    """Return the struct layout for a module, using a disk cache keyed by file hash.

    Args:
        ko_path (Path): Path to the ``.ko`` kernel object file.

    Returns:
        dict[str, KconfigStructFields]: Mapping of struct name to its field-to-type map.

    """
    rel_path = ko_path.relative_to(config.state.module_dir).as_posix()
    ko_stat = ko_path.stat()
    ko_signature = f"{ko_stat.st_mtime}_{ko_stat.st_size}"

    if rel_path in MODULE_CACHE:
        if MODULE_CACHE[rel_path].get("signature") == ko_signature:
            return MODULE_CACHE[rel_path]["layout"]

        ui.out_debug(f"Module '{ko_path.name}' recompiled, updating cache ...")

    layout = cache_module_structs(ko_path)
    MODULE_CACHE[rel_path] = {"signature": ko_signature, "layout": layout}
    return layout


def load_module_cache() -> None:
    """Load the module cache from disk, or build it if it's missing/invalid."""
    if not module_cache_file.exists():
        return

    try:
        with module_cache_file.open(encoding="utf-8") as f:
            data = json.load(f)

        MODULE_CACHE.clear()
        MODULE_CACHE.update(data)

        ui.out_debug(f"Loaded {len(MODULE_CACHE)} module layouts from disk.")
    except (json.JSONDecodeError, KeyError):
        ui.out_warning("Module cache corrupted, rebuilding ...")


def build_module_struct_cache() -> None:
    """Refresh the on-disk layout cache for all ``.ko`` files under ``module_root``."""
    load_module_cache()

    ko_files = list(config.state.module_dir.rglob("*.ko"))
    if not ko_files:
        ui.out_warning(f"No .ko files found in {config.state.module_dir}")
        return

    for file in ko_files:
        get_module_layout(file)

    with module_cache_file.open("w") as f:
        json.dump(MODULE_CACHE, f)
