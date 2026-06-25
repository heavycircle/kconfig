from __future__ import annotations

from tree_sitter import Node

KconfigQueryCapture = dict[str, list[Node]]
"""Captures for tree_sitter queries."""

KconfigQueryResult = list[tuple[int, KconfigQueryCapture]]
"""Results from tree_sitter queries."""

KconfigStructFields = dict[str, str]
"""Fields inside a structure. Represented as { name: type }."""

