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
