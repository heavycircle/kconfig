from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tree_sitter import Node


if TYPE_CHECKING:
    from pathlib import Path


KconfigQueryResult = dict[str, list[Node]]
"""Results from tree_sitter queries."""


@dataclass
class KconfigStructConfig:
    """Class to represent CONFIG options and their fields."""

    name: str
    fields: list[str] = field(default_factory=list)


@dataclass
class KconfigStruct:
    """Class to represent a found structure."""

    name: str
    body: bytes
    file: Path

    configs: list[KconfigStructConfig] = field(default_factory=list)


@dataclass
class KconfigSignature:
    """Class to represent extracted signatures."""

    name: str
    signature: str
    is_macro: bool
    file: Path

    # Extracted structures from the signature
    structs: list[str] = field(default_factory=list)
    unions: list[str] = field(default_factory=list)
    typedefs: list[str] = field(default_factory=list)
