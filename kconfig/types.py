from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from tree_sitter import Node

if TYPE_CHECKING:
    from pathlib import Path

    from sympy import Expr


KconfigQueryCapture = dict[str, list[Node]]
"""Captures for tree_sitter queries."""

KconfigQueryResult = list[tuple[int, KconfigQueryCapture]]
"""Results from tree_sitter queries."""

KconfigStructFields = dict[str, str]
"""Fields inside a structure. Represented as { name: type }."""


@dataclass
class KconfigResolvedType:
    """A resolved type."""

    true_type: str
    file: Path
    depends: KconfigFieldGuard | None = None


@dataclass
class KconfigFieldType:
    """The type of a field within a struct."""

    original_type: str
    resolved_type: list[KconfigResolvedType] = field(default_factory=list)
    layout: KconfigStruct | None = None


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


@dataclass
class KconfigStructField:
    """A field within a struct."""

    field_name: str
    field_type: KconfigFieldType

    depends: KconfigFieldGuard | None = None


@dataclass
class KconfigStruct:
    """A structure found inside the kernel."""

    original_name: str
    resolved_name: str
    file: Path

    fields: list[KconfigStructField] = field(default_factory=list)

    @property
    def dependencies(self) -> int:
        """Recursively count all nested struct dependencies.

        Returns:
            int: Total number of nested structs at all depths.

        """
        count = 1
        for child in self.fields:
            if child.field_type.layout is not None:
                count += child.field_type.layout.dependencies
        return count


@dataclass
class KconfigCustomMembers:
    """Class to represent custom members of code."""

    structs: set[str] = field(default_factory=set)
    unions: set[str] = field(default_factory=set)
    typedefs: set[str] = field(default_factory=set)

    @property
    def is_empty(self) -> bool:
        """Check if there are no custom members."""
        return not (self.structs or self.unions or self.typedefs)


@dataclass
class KconfigSignature:
    """Class to represent extracted signatures."""

    name: str
    signature: str
    is_macro: bool
    file: Path

    members: KconfigCustomMembers = field(default_factory=KconfigCustomMembers)


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
