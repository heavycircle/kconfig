from __future__ import annotations

from typing import NamedTuple

from tree_sitter import Node

KconfigQueryResult = dict[str, list[Node]]
"""Results from tree_sitter queries."""

class KconfigStruct(NamedTuple):
    """Tuple to represent a found structure."""

    name: str
    body: str

class KconfigStructConfig(NamedTuple):
    """Tuple to represent found CONFIG options and their fields."""

    name: str
    fields: list[str]
