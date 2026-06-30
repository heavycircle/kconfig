from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from sympy import Expr


@dataclass
class KconfigResolvedType:
    """A resolved type."""

    resolved_type: str
    file: Path
    guard: Expr

    # Recursive sub-fields
    layout: KconfigStruct | None = None


@dataclass
class KconfigFieldType:
    """The type of a field within a struct."""

    original_type: str
    resolved_types: list[KconfigResolvedType] = field(default_factory=list)

    # Recursive sub-fields
    layout: KconfigStruct | None = None


@dataclass
class KconfigStructField:
    """A field within a struct."""

    field_name: str
    field_type: KconfigFieldType

    guard: Expr


@dataclass
class KconfigStruct:
    """A structure found inside the kernel."""

    original_name: str
    file_path: Path
    file_line: int

    resolved_name: str = ""
    fields: list[KconfigStructField] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Match resolved_name or original_name if it's not unique."""
        if not self.resolved_name:
            self.resolved_name = self.original_name


# TODO: Remove
@dataclass
class KconfigFieldGuard:
    """A CONFIG guard changing whether a field is present."""

    # Base information
    name: str = ""
    is_enabled: bool = True

    # Recursing into sub-operations
    operand: str | None = None
    expression: list[KconfigFieldGuard] = field(default_factory=list)

    @property
    def is_expression(self) -> bool:
        """Check if this guard is an expression or a leaf node."""
        return self.operand is not None

    @property
    def is_impossible(self) -> bool:
        """Check if this guard is impossible to satisfy (sympy.false)."""
        return self.is_enabled is False and len(self.expression) == 0

    @property
    def is_guaranteed(self) -> bool:
        """Check if this guard is always valid (sympy.true)."""
        return self.is_enabled and len(self.expression) == 0

    @property
    def is_conditional(self) -> bool:
        """Check if this guard is conditionally true."""
        return not (self.is_impossible or self.is_guaranteed)

    def __str__(self) -> str:
        """Print the guard."""
        if self.is_expression and self.operand:
            s = f" {self.operand} ".join(str(x) for x in self.expression)
        else:
            s = self.name

        if self.is_enabled:
            return s

        if self.is_expression:
            return f"!({s})"
        return f"!{s}"
