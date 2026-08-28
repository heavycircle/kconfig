from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class KconfigModuleCapabilities:
    """What kconfig is able to introspect from a single compiled module/vmlinux file.

    Populated by ``core.cache.modules.probe_module`` -- the same probe both
    ``kconfig module info`` and ``cache_module_structs`` use, so a module's
    reported capabilities and its actual behavior in ``struct analyze``/
    ``signature analyze`` never disagree.
    """

    file: Path
    has_dwarf: bool
    has_btf: bool
    struct_layout_available: bool
    needs_btf_base: bool
    symtab_stripped: bool
    vermagic: str | None
    modinfo: dict[str, str] = field(default_factory=dict)

    @property
    def tier(self) -> str:
        """A short label for the best introspection tier actually available."""
        if self.struct_layout_available:
            return "split-btf" if self.needs_btf_base else "full"
        if self.vermagic:
            return "vermagic-only"
        return "none"
