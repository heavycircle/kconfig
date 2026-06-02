from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tree_sitter import Node

from kconfig.core import utils


if TYPE_CHECKING:
    from pathlib import Path


KconfigQueryCapture = dict[str, list[Node]]
"""Captures for tree_sitter queries."""

KconfigQueryResult = list[tuple[int, KconfigQueryCapture]]
"""Results from tree_sitte queries."""


@dataclass
class KconfigStructConfig:
    """Class to represent CONFIG options and their fields."""

    name: str
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class KconfigStruct:
    """Class to represent a found structure."""

    name: str
    body: bytes
    file: Path
    configs: list[KconfigStructConfig] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Normalize C code after instantiation."""
        self.body = utils.normalize_struct(self.body)


@dataclass
class KconfigSignature:
    """Class to represent extracted signatures."""

    name: str
    signature: str
    is_macro: bool
    file: Path

    # Extracted structures from the signature
    structs: set[str] = field(default_factory=set)
    unions: set[str] = field(default_factory=set)
    typedefs: set[str] = field(default_factory=set)


@dataclass
class KconfigStructComparison:
    """Class to represent a comparison between structures."""

    name: str

    enabled_configs: set[str] = field(default_factory=set)
    disabled_configs: set[str] = field(default_factory=set)
    order_mismatches: set[str] = field(default_factory=set)
    type_mismatches: set[str] = field(default_factory=set)

    @property
    def is_match(self) -> bool:
        """True if two structures match with no errors."""
        return not self.order_mismatches and not self.type_mismatches
