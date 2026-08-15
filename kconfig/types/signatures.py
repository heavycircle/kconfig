from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from sympy import Expr


@dataclass
class KconfigCustomMembers:
    """Custom members of a code snippet (normally a signature)."""

    structs: set[str] = field(default_factory=set)
    unions: set[str] = field(default_factory=set)
    typedefs: set[str] = field(default_factory=set)

    @property
    def is_empty(self) -> bool:
        """Check if there are no custom members."""
        return not (self.structs or self.unions or self.typedefs)


@dataclass
class KconfigSignature:
    """An extracted signature pulled from the kernel."""

    name: str
    signature: str
    is_macro: bool
    file: Path

    members: KconfigCustomMembers = field(default_factory=KconfigCustomMembers)


@dataclass
class KconfigMemberGuard:
    """A CONFIG guard found on a field, reached while walking one of a signature's custom members.

    Unlike KconfigEvidence, this reflects only what's structurally written in
    the kernel source (#ifdef nesting) -- no compiled-module comparison is
    involved.
    """

    member: str
    struct_name: str
    field_name: str
    guard: Expr
