from __future__ import annotations

from kconfig.core import parser, utils
from kconfig.utils import KconfigCustomMembers, KconfigStruct, KconfigStructConfig, sanitize_kernel_macros


def get_struct_configs(struct: KconfigStruct) -> list[KconfigStructConfig]:
    """Get a structure's source code from the kernel.

    Args:
        struct (KconfigStruct): Base struct information.

    Returns:
        list[KconfigStructConfig]: List of CONFIG options in this struct.

    """
    query = parser.get_query("struct-config")
    matches = parser.run_query(sanitize_kernel_macros(struct.body), query)

    configs: list[KconfigStructConfig] = []
    for _, captures in matches:
        # Ensure we have a valid capture.
        names = utils.get_capture_text(captures, "config.name")
        blocks = utils.get_capture_nodes(captures, "config.block")
        if not (names and blocks):
            continue

        # Add type dictionaries for the config.
        config = KconfigStructConfig(name=names[0].decode())
        for child in blocks[0].children:
            if child.type == "field_declaration":
                config.fields.update(utils.parse_field_declaration(child))

        configs.append(config)

    return configs


def get_custom_struct_members(code: bytes) -> KconfigCustomMembers:
    """Get custom struct members from code.

    This method works for many types of code, but is most often used in this
    application for function signatures and struct definitions.

    Args:
        code (bytes): Code to parse for return.

    Returns:
        KconfigCustomMembers: Custom members for this code.

    """
    structs, unions, typedefs = set[str](), set[str](), set[str]()
    for _, captures in parser.run_query(code, parser.get_query("signature-match")):
        structs.update(utils.get_node_text(n).decode() for n in captures.get("struct.name", []))
        unions.update(utils.get_node_text(n).decode() for n in captures.get("union.name", []))
        typedefs.update(utils.get_node_text(n).decode() for n in captures.get("typedef.name", []))

    typedefs = typedefs - structs - unions
    return KconfigCustomMembers(structs, unions, typedefs)
