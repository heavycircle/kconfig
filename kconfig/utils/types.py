from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tree_sitter import Node


if TYPE_CHECKING:
    from pathlib import Path


KconfigQueryCapture = dict[str, list[Node]]
"""Captures for tree_sitter queries."""

KconfigQueryResult = list[tuple[int, KconfigQueryCapture]]
"""Results from tree_sitte queries."""

KconfigStructFields = dict[str, str]
"""Fields inside a structure. Represented as { name: type }."""


@dataclass
class KconfigStructField:
    """A field within a struct."""

    field_name: str
    field_type: str

    depends: list[str] = field(default_factory=list)


@dataclass
class KconfigStruct:
    """A structure found inside the kernel."""

    name: str
    file: Path

    fields: list[KconfigStructField] = field(default_factory=list)
    nested: list[KconfigStruct] = field(default_factory=list)

    @property
    def dependencies(self) -> int:
        """Recursively count the struct's children."""
        count = len(self.nested)
        for child in self.nested:
            count += child.dependencies
        return count


@dataclass
class KconfigCustomMembers:
    """Class to represent custom members of code."""

    structs: set[str] = field(default_factory=set)
    unions: set[str] = field(default_factory=set)
    typedefs: set[str] = field(default_factory=set)


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

    def __str__(self) -> str:
        """Print the evidence for this config."""
        verb = "Found" if self.is_enabled else "Missing"
        return f"{verb} '{self.field_name}' in '{self.struct_name}'"


class KconfigAnalysis:
    """Aggregate all evidence and automatically flags conflicts."""

    def __init__(self) -> None:
        self.log: dict[str, list[KconfigConfigEvidence]] = defaultdict(list)

    def add_evidence(self, config_name: str, evidence: KconfigConfigEvidence) -> None:
        """Add a config report to the log."""
        self.log[config_name].append(evidence)

    @property
    def enabled_configs(self) -> dict[str, list[KconfigConfigEvidence]]:
        """Returns configs where ALL evidence points to True."""
        return {k: v for k, v in self.log.items() if all(e.is_enabled for e in v)}

    @property
    def disabled_configs(self) -> dict[str, list[KconfigConfigEvidence]]:
        """Returns configs where ALL evidence points to False."""
        return {k: v for k, v in self.log.items() if all(not e.is_enabled for e in v)}

    @property
    def conflicts(self) -> dict[str, list[KconfigConfigEvidence]]:
        """Returns configs where evidence contradicts itself."""
        results: dict[str, list[KconfigConfigEvidence]] = {}
        for config, evidence_list in self.log.items():
            states = {e.is_enabled for e in evidence_list}
            if len(states) > 1:
                results[config] = evidence_list
        return results
