from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sympy import Expr


@dataclass
class KconfigEvidence:
    """Represent a single piece of evidence for a config state."""

    struct_name: str
    field_name: str
    is_enabled: bool

    raw_guard: Expr
    constraints: Expr

    # Type-based evidence support
    kind: Literal["field", "type"] = "field"
    type: str | None = None

    def __str__(self) -> str:
        """Return a human-readable string describing this evidence."""
        if self.kind == "type":
            return f"Type of '{self.field_name}' matched '{self.type}' in '{self.struct_name}'"

        verb = "Found" if self.is_enabled else "Missing"
        return f"{verb} '{self.field_name}' in '{self.struct_name}'"

