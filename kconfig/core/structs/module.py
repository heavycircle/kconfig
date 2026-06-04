from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from kconfig.utils import KconfigFileInvalidError, KconfigStruct


if TYPE_CHECKING:
    from pathlib import Path


def get_module_struct(ko_path: Path, struct_name: str) -> KconfigStruct:
    """Get a struct's source from a kernel module.

    Args:
        ko_path (Path): Path to the kernel module.
        struct_name (str): Name of the structure.

    Returns:
        list[str]: Items found in the structure.

    """
    for file in utils.find_candidate_kernel_modules(module_root, struct_name):
        layout = get_module_layout(file)
        if struct_name in layout:
            reurn layout[struct_name]

    raise KconfigSymbolNotFoundError(struct_name, module_root)

def _build_module_cache(ko_path: Path) -> dict[str, KconfigStructFields]:
    """Build the cache of module structures."""
    ui.out_debug(f"Building module cache for '{ko_path}' ...")

    cmd = ["pahole", str(ko_path)]
    result = subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
    if result.returncode != 0 or not result.stdout.strip():
        raise KconfigSubprocessFailedError("pahole", result.stderr.decode().strip())

    cache: dict[str, KconfigStructFields] = {}
    for _, captures in parser.run_query(result.stdout, parser.get_query("struct-list")):
        name_node = utils.get_capture_text(captures, "struct.name")
        def_node = utils.get_capture_text(captures, "struct.def")
        if not (name_node and def_node):
            continue

        struct = KconfigStruct(name_node[0].decode(), def_node[0], ko_path)
        fields = utils.get_struct_members(struct)
        cache[struct.name] = fields

    return cache


def get_module_layout(ko_path: Path) -> dict[str, KconfigStructFields]:
    """Fetch module layout from disk cache, or build if stale/missing."""
    module_dir = CACHE_DIR / "modules"
    module_dir.mkdir(parents=True, exist_ok=True)

    safe_name = str(ko_path.resolve()).replace("/", "_") + ".json"
    file_sum = hashlib.sha256(ko_path.read_bytes()).hexdigest()

    cache_file = module_dir / safe_name
    if cache_file.exists():
        with cache_file.open(encoding="utf-8") as f:
            cache_data = json.load(f)

        if file_sum == cache_data["sha256"]:
            ui.out_debug(f"Using cached module layout: {ko_path}")
            return cache_data["layout"]

    layout = _build_module_cache(ko_path)
    with cache_file.open("w", encoding="utf-8") as f:
        json.dump({"sha256": file_sum, "layout": layout}, f)

    return layout


def get_module_capabilities(module_root: Path) -> None:
    """Refresh the cache of module capabilities."""
    total_files = sum(1 for f in module_root.rglob("*.ko") if f.is_file())
    ui.out_info(f"Refreshing the cache for {total_files} module ...")

    for file in module_root.rglob("*.ko"):
        get_module_layout(file)
