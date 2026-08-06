from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from kconfig.core.analysis.structs import EVALUATION_CACHE
from kconfig.core.cache.modules import MODULE_CACHE
from kconfig.core.cache.structs import ALIAS_CACHE, STRUCT_CACHE
from kconfig.core.cache.typedefs import TYPEDEF_CACHE
from kconfig.core.config import kconfig_state
from kconfig.core.parser import dispatch
from kconfig.core.parser.field_declaration import STRUCT_MEMO_CACHE
from kconfig.core.parser.typedefs import TYPEDEF_RESOLVE_CACHE
from kconfig.core.query.query import parse_source
from kconfig.types import KconfigParserState

if TYPE_CHECKING:
    from pathlib import Path

    from tree_sitter import Node


@pytest.fixture(autouse=True)
def _reset_module_caches() -> None:
    """Clear every module-level cache so tests can't leak state into each other."""
    EVALUATION_CACHE.clear()
    MODULE_CACHE.clear()
    ALIAS_CACHE.clear()
    STRUCT_CACHE.clear()
    TYPEDEF_CACHE.clear()
    TYPEDEF_RESOLVE_CACHE.clear()
    STRUCT_MEMO_CACHE.clear()


@pytest.fixture
def kernel_dir(tmp_path: Path) -> Path:
    """Point ``kconfig_state`` at an empty, writable directory standing in for a kernel checkout.

    The on-disk location caches (``core/cache/*.py``) key their pickle files
    by ``kernel_dir.name`` alone. Pytest's ``tmp_path`` reuses the same
    test-derived basename across separate ``pytest`` invocations, which can
    collide with a stale cache file from an earlier run pointing at a
    since-deleted directory. A random subdirectory name sidesteps that.
    """
    unique_dir = tmp_path / uuid.uuid4().hex
    unique_dir.mkdir()
    kconfig_state.kernel_dir = unique_dir
    return unique_dir


def parse_and_dispatch(source: bytes, *, recursive: bool = False) -> KconfigParserState:
    """Parse a C snippet and run it through the dispatcher, returning the resulting state."""
    state = KconfigParserState(recursive=recursive)
    dispatch.dispatch(parse_source(source), state)
    return state


def _find_node_or_none(node: Node, node_type: str) -> Node | None:
    if node.type == node_type:
        return node

    for child in node.children:
        found = _find_node_or_none(child, node_type)
        if found is not None:
            return found

    return None


def find_node(node: Node, node_type: str) -> Node:
    """Find the first descendant (or self) node of a given type."""
    found = _find_node_or_none(node, node_type)
    if found is None:
        raise ValueError(f"No '{node_type}' node found")

    return found
