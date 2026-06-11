from __future__ import annotations

import json
from pathlib import Path

from kconfig.core import config, parser, utils
from kconfig.ui import ui

from .config import CACHE_STRUCT_DIR


STRUCT_CACHE: dict[str, set[Path]] = {}
struct_path_file = CACHE_STRUCT_DIR / "cache_struct_paths.json"


def cache_struct_locations() -> None:
    """Cache the struct locations of all structs inside the kernel.

    This method can take a while. It's persistent across runs.

    """
    ui.out_info("Warming the struct location cache (this may take a minute)...")
    STRUCT_CACHE.clear()

    for path in config.state.kernel_dir.rglob("*.[ch]"):
        contents = path.read_bytes()
        for _, captures in parser.run_query("struct-list", contents):
            struct_names = utils.get_capture_text(captures, "struct.name")
            if not struct_names:
                continue

            found_name = struct_names[0].decode()

            # Store the ABSOLUTE path in memory for the engine to use right now
            STRUCT_CACHE.setdefault(found_name, set()).add(path)

    serial_cache: dict[str, list[str]] = {}
    for struct_name, paths in STRUCT_CACHE.items():
        serial_cache[struct_name] = [p.relative_to(config.state.kernel_dir).as_posix() for p in paths]

    payload = {"kernel_dir": config.state.kernel_dir.as_posix(), "structs": serial_cache}
    struct_path_file.parent.mkdir(parents=True, exist_ok=True)
    with struct_path_file.open("w") as f:
        json.dump(payload, f)

    ui.out_success(f"Cached locations for {len(serial_cache)} structs!")


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

        ui.out_debug(f"Loaded {len(STRUCT_CACHE)} structs from disk cache.")

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


def resolve_target_file(candidate_files: list[Path]) -> Path | None:
    """Filters multiple struct definitions down to the single correct file."""
    return min(candidate_files, key=_rank_file, default=None)


def get_struct_location(struct_name: str) -> Path | None:
    """Finds the definition file for a struct."""
    if struct_name not in STRUCT_CACHE:
        return None

    locations = list(STRUCT_CACHE[struct_name])
    if len(locations) == 1:
        return locations[0]

    return resolve_target_file(locations)
