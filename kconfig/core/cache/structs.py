from __future__ import annotations

import json
from pathlib import Path

from kconfig.core import config, parser, utils
from kconfig.types import KconfigStruct
from kconfig.ui import ui

from .config import CACHE_STRUCT_DIR


STRUCT_CACHE: dict[str, set[Path]] = {}
ALIAS_CACHE: dict[str, str] = {}

struct_path_file = CACHE_STRUCT_DIR / "cache_struct_paths.json"


def cache_struct_locations() -> None:
    """Cache the struct locations of all structs inside the kernel.

    This method can take a while. It's persistent across runs.

    """
    ui.out_info("Warming the struct location cache (this may take a minute)...")
    STRUCT_CACHE.clear()
    ALIAS_CACHE.clear()

    for path in config.state.kernel_dir.rglob("*.[ch]"):
        contents = path.read_bytes()
        for _, captures in parser.run_query("struct-list", contents):
            struct_names = utils.get_capture_text(captures, "struct.name")
            if not struct_names:
                continue

            found_name = struct_names[0].decode()
            STRUCT_CACHE.setdefault(found_name, set()).add(path)

        for _, captures in parser.run_query("alias-find", contents):
            alias_names = utils.get_capture_text(captures, "alias.name")
            alias_targets = utils.get_capture_text(captures, "alias.target")
            if not (alias_names and alias_targets):
                continue

            name = alias_names[0].decode(encoding="utf-8", errors="replace")
            target = alias_targets[0].decode(encoding="utf-8", errors="replace")
            ALIAS_CACHE[name] = target

    # Serialize struct information
    serial_cache: dict[str, list[str]] = {}
    for struct_name, paths in STRUCT_CACHE.items():
        serial_cache[struct_name] = [p.relative_to(config.state.kernel_dir).as_posix() for p in paths]

    payload = {
        "kernel_dir": config.state.kernel_dir.as_posix(),
        "structs": serial_cache,
        "aliases": ALIAS_CACHE,
    }
    with struct_path_file.open("w") as f:
        json.dump(payload, f)

    ui.out_success(f"Cached locations for {len(STRUCT_CACHE)} structs and {len(ALIAS_CACHE)} aliases!")


def build_struct_location_cache() -> None:
    """Loads the cache from disk, or builds it if invalid/missing."""
    if not struct_path_file.exists():
        cache_struct_locations()
        return

    try:
        with struct_path_file.open("r") as f:
            payload = json.load(f)

        if payload.get("kernel_dir") != config.state.kernel_dir.as_posix():
            ui.out_warning("Kernel directory changed. Rebuilding cache...")
            cache_struct_locations()
            return

        STRUCT_CACHE.clear()
        for struct_name, rel_paths in payload.get("structs", {}).items():
            STRUCT_CACHE[struct_name] = {config.state.kernel_dir / Path(p) for p in rel_paths}

        ALIAS_CACHE.clear()
        ALIAS_CACHE.update(payload.get("aliases", {}))

        ui.out_debug(f"Loaded {len(STRUCT_CACHE)} structs and {len(ALIAS_CACHE)} aliases from disk cache.")

    except (json.JSONDecodeError, KeyError, TypeError):
        ui.out_warning("Cache file corrupted. Rebuilding...")
        cache_struct_locations()


def _rank_file(path: Path) -> tuple[int, int, str]:
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
    """Finds the definition file for a struct."""
    true_name = ALIAS_CACHE.get(struct_name, struct_name)
    if true_name != struct_name:
        ui.out_debug(f"Resolved alias: {struct_name} -> {true_name}")

    if true_name not in STRUCT_CACHE:
        return None

    locations = list(STRUCT_CACHE[true_name])
    if len(locations) == 1:
        return KconfigStruct(struct_name, true_name, locations[0])

    return KconfigStruct(struct_name, true_name, min(locations, key=_rank_file))
