from __future__ import annotations

from pathlib import Path


CACHE_DIR = Path.home() / ".cache" / "kconfig"
"""Base directory for this project's cache."""

CACHE_KERNEL_DIR = CACHE_DIR / "kernel"
"""Base directory for storing kernel files."""

CACHE_MODULE_DIR = CACHE_DIR / "modules"
"""Base directory for storing hashes for kernel modules."""

CACHE_STRUCT_DIR = CACHE_DIR / "structs"
"""Base directory for storing kernel struct definitions."""


# Ensure they all exist
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_KERNEL_DIR.mkdir(parents=True, exist_ok=True)
CACHE_STRUCT_DIR.mkdir(parents=True, exist_ok=True)
