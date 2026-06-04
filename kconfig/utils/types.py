from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tree_sitter import Node

from kconfig.core import utils
from .normalize import normalize_struct

if TYPE_CHECKING:
    from pathlib import Path


KconfigQueryCapture = dict[str, list[Node]]
"""Captures for tree_sitter queries."""

KconfigQueryResult = list[tuple[int, KconfigQueryCapture]]
"""Results from tree_sitte queries."""

KconfigStructFields = dict[str, str]
"""Fields inside a structure. Represented as { name: type }."""

@dataclass
class KconfigStructConfig:
    """Class to represent CONFIG options and their fields."""

    name: str
    fields: KconfigStructFields = field(default_factory=KconfigStructFields)


@dataclass
class KconfigStruct:
    """Class to represent a found structure."""

    name: str
    body: bytes
    file: Path
    fields: KconfigStructFields = field(default_factory=KconfigStructFields)
    configs: list[KconfigStructConfig] = field(default_factory=list)
    nested_structs: list[KconfigStruct] = field(default_factory=list)

    @property
    def nested_count(self) -> int:
        """Recursively count the struct's children."""
        count = len(self.nested_structs)
        for child in self.nested_structs:
            count += child.nested_count
        return count

    def __post_init__(self) -> None:
        """Normalize C code after instantiation."""
        self.body = normalize_struct(self.body)


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
class KconfigEvidence:
    """Represent a single piece of evidence for a config state."""
    
    struct_name: str
    field_name: str
    is_enabled: bool
    
    def __str__(self):
        state = "ENABLED" if self.is_enabled else "DISABLED"
        verb = "Found" if self.is_enabled else "Missing"
        return f"[{state}] {verb} '{self.field_name}' in '{self.struct_name}'"


class AnalysisReport:
    """Aggregate all evidence and automatically flags conflicts."""
    
    def __init__(self):
        self.log: dict[str, list[KconfigEvidence]] = defaultdict(list)

    def add_evidence(self, config_name: str, evidence: KconfigEvidence):
        self.log[config_name].append(evidence)

    @property
    def enabled_configs(self) -> dict[str, list[KconfigEvidence]]:
        """Returns configs where ALL evidence points to True."""
        return {k: v for k, v in self.log.items() if all(e.is_enabled for e in v)}

    @property
    def disabled_configs(self) -> dict[str, list[KconfigEvidence]]:
        """Returns configs where ALL evidence points to False."""
        return {k: v for k, v in self.log.items() if all(not e.is_enabled for e in v)}

    @property
    def conflicts(self) -> dict[str, list[KconfigEvidence]]:
        """Returns configs where evidence contradicts itself."""
        results = {}
        for config, evidence_list in self.log.items():
            states = {e.is_enabled for e in evidence_list}
            if len(states) > 1:
                results[config] = evidence_list
        return results
