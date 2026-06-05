from __future__ import annotations

from kconfig.core import parser, utils
from kconfig.utils import KconfigCustomMembers

if TYPE_CHECKING:
    from tree_sitter import Node


# TODO: Move to parser/utils
def get_custom_struct_members(source: Node) -> KconfigCustomMembers:
    """Get custom struct members from code.

    This method works for many types of code, but is most often used in this
    application for function signatures and struct definitions.

    Args:
        code (Node): Code to parse for return.

    Returns:
        KconfigCustomMembers: Custom members for this code.

    """
    structs, unions, typedefs = set[str](), set[str](), set[str]()
    captures = parser.run_query(source, "signature-match")
    structs.update(utils.get_node_text(n).decode() for n in captures.get("struct.name", []))
    unions.update(utils.get_node_text(n).decode() for n in captures.get("union.name", []))
    typedefs.update(utils.get_node_text(n).decode() for n in captures.get("typedef.name", []))

    typedefs = typedefs - structs - unions
    return KconfigCustomMembers(structs, unions, typedefs)
