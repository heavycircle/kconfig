from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser
from kconfig.utils.exceptions import KconfigQueryImpossibleError
from kconfig.utils.types import KconfigStruct, KconfigStructConfig


if TYPE_CHECKING:
    from pathlib import Path


def find_struct(file: Path, struct_name: str) -> KconfigStruct:
    """Find a structure by name inside a C file.

    Args:
        file (Path): Path to the C file to query.
        struct_name (str): Name of the structure to find.

    Raises:
        KconfigFileError: Missing C or Query (SCM) file.

    Returns:
        KconfigStruct: Matching structure inside source file.

    """
    query = parser.get_query("find-struct").replace("__STRUCT_NAME__", struct_name)

    result = parser.run_file_query(file, query)
    return KconfigStruct(
        name=parser.get_single_node_text(result, "struct.name"),
        body=parser.get_single_node_text(result, "struct.def"),
    )


def find_struct_configs(struct_code: bytes) -> list[KconfigStructConfig]:
    """Find configurable options inside a structure.

    Args:
        struct_code (bytes): Structure to parse.

    Returns:
        list[KconfigStructConfig]: List of Config and field structures.

    """
    query = parser.get_query("ifdef-struct")
    result = parser.run_query(struct_code, query)

    struct_name = parser.get_single_node(result, "struct.name")
    config_names = parser.get_nodes(result, "config.name")
    config_block = parser.get_nodes(result, "config.block")

    configs: list[KconfigStructConfig] = []
    # Iterate through all found configs
    for name, block in zip(config_names, config_block, strict=True):
        if not name.text:
            raise KconfigQueryImpossibleError(f"Impossible: Missing config name: {struct_name}")

        config = KconfigStructConfig(name=name.text.decode("utf-8"), fields=[])
        # Get the children found in the config.block
        for child in block.children:
            if child.type != "field_declaration":
                continue

            if not child.text:
                raise KconfigQueryImpossibleError(f"Impossible: Missing config body: {struct_name}")
            config.fields.append(parser.normalize_field(child.text.decode("utf-8")))

        configs.append(config)

    return configs
