from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .exceptions import KconfigInvalidArgumentError, KconfigMissingArgumentError


CACHE_DIR = Path.home() / ".cache" / "kconfig"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class KconfigState:
    """Centralized state for the application."""

    def __init__(self) -> None:
        # Private backing variables
        self._kernel_dir = Path
        self._module_dir = Path

    def _check_kernel_dir(self, kernel_dir: Path) -> None:
        if not kernel_dir.exists():
            raise KconfigInvalidArgumentError(version, "Missing kernel directory")
        if not kernel_dir.is_dir():
            raise KconfigMissingArgumentError(version, "Not a directory")

    @property
    def kernel_version(self) -> str | None:
        """Kernel version."""
        return self._kernel_version

    @kernel_version.setter
    def kernel_version(self, version: str | None) -> None:
        if version is None:
            raise KconfigMissingArgumentError("kernel_version")

        kernel_dir = CACHE_DIR / "kernel" / f"linux-{version}"
        self._check_kernel_dir(kernel_dir)

        self._kernel_version = version
        self._kernel_dir = kernel_dir

    @property
    def kernel_dir(self) -> Path:
        return self._kernel_dir

    @kernel_dir.setter
    def kernel_dir(self, path: str | Path | None) -> None:
        if path is None:
            raise KconfigMissingArgumentError("kernel_dir")

        p = Path(path).resolve()
        self._check_kernel_dir(p)

        self._kernel_dir = p

    @property
    def module_dir(self) -> Path:
        """Directory containing reference kernel modules."""
        return self._module_dir

    @module_dir.setter
    def module_dir(self, path: Path | str) -> None:
        p = Path(path).resolve()
        if not p.exists():
            raise KconfigInvalidArgumentError(p.name, "No such file or directory")

        self._module_dir = p


state = KconfigState()
