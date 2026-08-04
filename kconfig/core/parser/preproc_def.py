from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.exceptions import KconfigASTAnomalyError
from kconfig.types import KconfigFieldType

from .dispatcher import NodeDispatch, dispatch

if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigParserState


@dispatch.register("preproc_def")
def parse_preproc_def(node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> None:  # noqa: ARG001
    """Parse a ``preproc_def`` node.

    Records a ``#define NAME VALUE`` as a field, so a macro-based typedef
    alias (e.g. ``#define Elf_Sym Elf64_Sym``) is tracked the same way a
    struct field is: guarded by whatever CONFIG conditions are active on
    the stack when it's encountered.

    Args:
        node (Node): The tree-sitter node to process.
        state (KconfigParserState): The current state of processing.
        dispatcher (NodeDispatch): The dispatcher to call child nodes.

    Raises:
        KconfigASTAnomalyError: Node is missing a ``name`` field.

    """
    name_node = node.child_by_field_name("name")
    if not name_node or not name_node.text:
        raise KconfigASTAnomalyError(node.type, "Missing 'name' field")

    value_node = node.child_by_field_name("value")
    if not value_node or not value_node.text:
        return  # Flag-only define (e.g. `#define FOO`), not a type alias.

    state.record_field(name_node.text.decode(), KconfigFieldType(value_node.text.decode()))
