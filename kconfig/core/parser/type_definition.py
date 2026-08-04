from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.exceptions import KconfigASTAnomalyError
from kconfig.types import KconfigFieldType

from .dispatcher import NodeDispatch, dispatch
from .field_declaration import unwrap_declarator

if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigParserState


@dispatch.register("type_definition")
def parse_type_definition(node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> None:  # noqa: ARG001
    """Parse a ``type_definition`` node.

    Records a ``typedef TYPE NAME;`` as a field, so a real typedef (e.g.
    ``typedef struct __kernel_foo foo;``) is tracked the same way a struct
    field is: guarded by whatever CONFIG conditions are active on the stack
    when it's encountered.

    Args:
        node (Node): The tree-sitter node to process.
        state (KconfigParserState): The current state of processing.
        dispatcher (NodeDispatch): The dispatcher to call child nodes.

    Raises:
        KconfigASTAnomalyError: Node is missing a ``type`` or ``declarator`` field.

    """
    type_node = node.child_by_field_name("type")
    declarator_node = node.child_by_field_name("declarator")
    if not type_node or not type_node.text or not declarator_node:
        raise KconfigASTAnomalyError(node.type, "Missing 'type' or 'declarator' field")

    mods, name = unwrap_declarator(declarator_node)
    full_type = " ".join(f"{type_node.text.decode()} {mods}".strip().split())
    state.record_field(name, KconfigFieldType(full_type))
