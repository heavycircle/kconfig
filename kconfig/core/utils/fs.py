from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Generator, Sequence


def _scan_files_priority(phrases: Sequence[tuple[Path, str]], symbol_name: str) -> Generator[Path]:
    """Scan paths in priority order, ensuring no duplicate reads.

    Args:
        phrases (Sequence[tuple[Path, str]]): Priority list of search files.
        symbol_name (str): Symbol to search for.

    Yields:
        Path: Path that might contain the symbol's definition.

    """
    symbol_bytes = symbol_name.encode()
    seen_files = set[Path]()

    for search_dir, pattern in phrases:
        if not search_dir.exists():
            continue

        for path in search_dir.rglob(pattern):
            if path in seen_files:
                continue
            seen_files.add(path)

            try:
                if symbol_bytes in path.read_bytes():
                    yield path
            except (PermissionError, FileNotFoundError):
                continue


def find_candidate_function_files(kernel_root: Path, function_name: str) -> Generator[Path]:
    """Optimized search for function signatures inside the kernel.

    Priority order:
        1. Source files - The function's definition.
        2. Global headers - Static functions and inline macros.
        3. Local headers - Subsystem-specific inlines.

    Args:
        kernel_root (Path): Path to the kernel root.
        function_name (str): The function to search for.

    Yields:
        Path: Files that might contain the function signature.

    """
    phrases = [
        (kernel_root, "*.c"),
        (kernel_root / "include", "*.h"),
        (kernel_root, "*.h"),
    ]
    return _scan_files_priority(phrases, function_name)


def find_candidate_struct_files(kernel_root: Path, struct_name: str) -> Generator[Path]:
    """Optimized search for struct definitions inside the kernel.

    Priority order:
        1. Global headers - Most definitions are here.
        2. Arch headers - Architecture specific structs.
        3. Local headers - Private subsystem structs.
        4. Source files - Private or opaque structs.

    Args:
        kernel_root (Path): Path to the kernel root.
        function_name (str): The function to search for.

    Yields:
        Path: Files that might contain the struct definition.

    """
    phrases = [
        (kernel_root / "include", "*.h"),
        (kernel_root / "arch", "*.h"),
        (kernel_root, "*.h"),
        (kernel_root, "*.c"),
    ]
    return _scan_files_priority(phrases, struct_name)


def find_candidate_kernel_modules(module_root: Path, symbol_name: str) -> Generator[Path]:
    """Optimized search for struct definitions inside the kernel.

    Args:
        module_root (Path): Path to the kernel modules root.
        symbol_name (str): The symbol to search for.

    Yields:
        Path: Files that might contain the struct definition.

    """
    return _scan_files_priority([(module_root), "*.ko")], symbol_name)
