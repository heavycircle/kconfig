from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Generator


def find_candidate_files(root: str, symbol_name: str) -> Generator[Path]:
    """Find files that might contain the definition of the symbol.

    Args:
        root (str): Base directory to search for files.
        symbol_name (str): Name of the symbol to find.

    Yields:
        Path: Path to the file possibly containing the symbol definition.

    """
    symbol_bytes = symbol_name.encode("utf-8")

    for path in Path(root).rglob("*.c"):
        try:
            if symbol_bytes in path.read_bytes():
                yield path
        except (PermissionError, FileNotFoundError):
            continue
