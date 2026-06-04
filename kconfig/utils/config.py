from __future__ import annotations

from pathlib import Path

CACHE_DIR = Path.home() / ".config" / "kconfig"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
