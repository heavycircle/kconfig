from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


def _find_candidate_files(root: Path, pattern: str, symbol_name: str) -> Generator[Path]:
    """Find header files that might contain the definition of the symbol.

    Args:
        root (str): Base directory to search for files.
        pattern (str): Pattern to glob for.
        symbol_name (str): Name of the symbol to find.

    Yields:
        Path: Path to the file possibly containing the symbol definition.

    """
    symbol_bytes = symbol_name.encode("utf-8")

    for path in root.rglob(pattern):
        try:
            if symbol_bytes in path.read_bytes():
                yield path
        except (PermissionError, FileNotFoundError):  # noqa: PERF203
            continue


def find_candidate_source_files(kernel_root: Path, symbol_name: str) -> Generator[Path]:
    """Find source files that might contain the definition of the symbol.

    Args:
        kernel_root (Path): Base directory to search for files.
        symbol_name (str): Name of the symbol to find.

    Yields:
        Path: Path to the file possibly containing the symbol definition.

    """
    return _find_candidate_files(kernel_root, "*.c", symbol_name)


def find_candidate_header_files(kernel_root: Path, symbol_name: str) -> Generator[Path]:
    """Find source files that might contain the definition of the symbol.

    Args:
        kernel_root (Path): Base directory to search for files.
        symbol_name (str): Name of the symbol to find.

    Yields:
        Path: Path to the file possibly containing the symbol definition.

    """
    return _find_candidate_files(kernel_root / "include", "*.h", symbol_name)
