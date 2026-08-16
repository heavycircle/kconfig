from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.types import KconfigCustomMembers

if TYPE_CHECKING:
    from tree_sitter import Node

TAG_FIELDS = {"struct_specifier": "structs", "union_specifier": "unions"}


def _collect_custom_members(node: Node, members: KconfigCustomMembers) -> None:
    tag_set_name = TAG_FIELDS.get(node.type)
    if tag_set_name:
        name_node = node.child_by_field_name("name")
        if name_node and name_node.text:
            getattr(members, tag_set_name).add(name_node.text.decode())

        for child in node.children:
            if child != name_node:
                _collect_custom_members(child, members)
        return

    if node.type == "type_identifier" and node.text:
        members.typedefs.add(node.text.decode())

    # A function's body is its implementation, not its exported interface --
    # genksyms/modversions computes a symbol's CRC from its declared return
    # type and parameter list only (recursively expanding types reachable
    # from *those*), never from types that merely appear in local variables,
    # casts, or macro expansions inside the function body. Skipping it here
    # keeps a signature's reported members limited to what could actually
    # explain a modversions CRC mismatch.
    skip = node.child_by_field_name("body") if node.type == "function_definition" else None
    for child in node.children:
        if child != skip:
            _collect_custom_members(child, members)


def get_custom_members(node: Node) -> KconfigCustomMembers:
    """Collect the struct/union tags and typedef names referenced within a node.

    Struct/union tag names (e.g. the ``foo`` in ``struct foo *``) are parsed
    as a ``type_identifier`` in the same way a typedef name is, so a plain
    tag/typedef isn't enough to tell them apart. This walks the tree
    structurally instead: a ``type_identifier`` only counts as a typedef
    reference when it isn't the ``name`` field of a struct/union specifier.

    If ``node`` is a ``function_definition``, its body is excluded -- only
    the return type and parameter list (its exported interface) are scanned.
    A macro's definition has no such split (the whole thing is scanned) since
    a macro has no separate declared interface.

    Args:
        node (Node): The tree-sitter node to scan (e.g. a function or macro definition).

    Returns:
        KconfigCustomMembers: The struct, union, and typedef names referenced within ``node``.

    """
    members = KconfigCustomMembers()
    _collect_custom_members(node, members)
    return members
