from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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
class KconfigFieldType:
    """The type of a field within a struct."""

    original_type: str
    resolved_type: str | None = None

    layout: KconfigStruct | None = None

    @property
    def is_complex(self) -> bool:
        """Check if this field type is anonymous/inline."""
        return self.layout is not None


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

    def __str__(self) -> str:
        """Print the guard."""
        if self.is_expression and self.operand:
            s = f" {self.operand} ".join(str(x) for x in self.expression)
        else:
            s = self.name

        if self.is_enabled:
            return s

        if self.is_expression:
            return f"~({s})"
        return f"~{s}"


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
class KconfigConfigEvidence:
    """Represent a single piece of evidence for a config state."""

    struct_name: str
    field_name: str
    is_enabled: bool

    raw_guard: Expr
    constraints: Expr

    def __str__(self) -> str:
        """Return a human-readable string describing this evidence.

        Returns:
            str: Evidence description including struct name, field name, and state.

        """
        verb = "Found" if self.is_enabled else "Missing"
        return f"{verb} '{self.field_name}' in '{self.struct_name}'"


class KconfigAnalysis:
    """Aggregate all evidence and automatically flags conflicts."""

    def __init__(self) -> None:
        self.log: dict[str, list[KconfigConfigEvidence]] = defaultdict(list)

    def add_evidence(self, config_name: str, evidence: KconfigConfigEvidence) -> None:
        """Add a config report to the log.

        Args:
            config_name (str): Name of the CONFIG option (e.g. ``CONFIG_FOO``).
            evidence (KconfigConfigEvidence): Evidence entry to record.

        """
        self.log[config_name].append(evidence)

    @property
    def enabled_configs(self) -> dict[str, list[KconfigConfigEvidence]]:
        """Configs where ALL evidence points to True.

        Returns:
            dict[str, list[KconfigConfigEvidence]]: Mapping of config name to its evidence list.

        """
        return {k: v for k, v in self.log.items() if all(e.is_enabled for e in v)}

    @property
    def disabled_configs(self) -> dict[str, list[KconfigConfigEvidence]]:
        """Configs where ALL evidence points to False.

        Returns:
            dict[str, list[KconfigConfigEvidence]]: Mapping of config name to its evidence list.

        """
        return {k: v for k, v in self.log.items() if all(not e.is_enabled for e in v)}

    @property
    def conflicts(self) -> dict[str, list[KconfigConfigEvidence]]:
        """Configs where evidence contradicts itself (mixed True/False).

        Returns:
            dict[str, list[KconfigConfigEvidence]]: Mapping of config name to its conflicting evidence list.

        """
        results: dict[str, list[KconfigConfigEvidence]] = {}
        for config, evidence_list in self.log.items():
            states = {e.is_enabled for e in evidence_list}
            if len(states) > 1:
                results[config] = evidence_list
        return results
