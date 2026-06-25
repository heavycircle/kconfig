from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core.utils import NodeDispatch, dispatcher
from kconfig.exceptions import KconfigASTAnomalyError

if TYPE_CHECKING:
    from tree_sitter import Node

    from kconfig.types import KconfigParserState


def unwrap_declarator(node: Node) -> tuple[str, str]:
    """Dig into a declarator node to separate a name from the type modifiers.

    This method intentionally does not attempt to parse ``function_declarator``
    nodes. They show up almost identically inside ``pahole``.

    Args:
        node (Node): The tree-sitter node to process.

    Raises:
        KconfigASTAnomalyError: Declarators missing ``declarator`` field.

    Returns:
        tuple[str, str]: A tuple contianing (modifiers, name).

    """
    if not node.text:
        return "", ""

    match node.type:
        case "pointer_declarator":
            nested = node.child_by_field_name("declarator")
            if not nested:
                raise KconfigASTAnomalyError(node.type, "Missing 'declarator' field")
            mods, name = unwrap_declarator(nested)

            mods = f"*{mods}"
        case "array_declarator":
            nested = node.child_by_field_name("declarator")
            if not nested:
                raise KconfigASTAnomalyError(node.type, "Missing 'declarator' field")
            mods, name = unwrap_declarator(nested)

            size_node = node.child_by_field_name("size")
            size_str = f"[{size_node.text.decode()}]" if size_node and size_node.text else "[]"
            mods = f"{mods}{size_str}"
        case _:  # Fallback: No type modifiers (identifier, field_identifier, function_declarator, ...)
            mods, name = "", node.text.decode()

    return mods, name


@dispatcher.register("field_declaration")
def parse_field_declaration(node: Node, state: KconfigParserState, dispatcher: NodeDispatch) -> None:  # noqa: ARG001
    """Parse a ``field_declaration`` node.

    This method records the current node inside the current state. Reaching a
    field_declaration means we've reached a field of the structure.

    Args:
        node (Node): The tree-sitter node to process.
        state (KconfigParserState): The current state of processing.
        dispatcher (NodeDispatch): The dispatcher to call child nodes.

    Raises:
        KconfigASTAnomalyError: Node is missing a type field.

    """
    type_node = node.child_by_field_name("type")
    if not type_node or not type_node.text:
        raise KconfigASTAnomalyError(node.type, "Missing 'type' field")
    base_type = type_node.text.decode()

    declarator_node = node.child_by_field_name("declarator")
    if not declarator_node:
        mods, name = "", f"anonymous_{node.id}"
    else:
        mods, name = unwrap_declarator(declarator_node)

    full_type = " ".join(f"{base_type} {mods}".strip().split())
    state.record_field(name, full_type)
