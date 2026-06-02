from __future__ import annotations

from kconfig.core import parser, utils
from kconfig.utils import KconfigQueryImpossibleError, KconfigStruct, KconfigStructConfig


def get_struct_configs(struct: KconfigStruct) -> KconfigStruct:
    """Get a structure's source code from the kernel.

    Args:
        struct (KconfigStruct): Base struct information.

    Returns:
        KconfigStruct: Complete struct information with config values.

    """
    query = parser.get_query("struct-config")
    result = parser.run_query(struct.body, query)

    config_names = utils.get_nodes(result, "config.name")
    config_block = utils.get_nodes(result, "config.block")

    for name, block in zip(config_names, config_block, strict=True):
        if not name.text:
            raise KconfigQueryImpossibleError(f"Impossible: Missing config name: {struct.name}")

        config = KconfigStructConfig(name=name.text.decode("utf-8"), fields=[])
        for child in block.children:
            if child.type != "field_declaration":
                continue

            if not child.text:
                raise KconfigQueryImpossibleError(f"Impossible: Missing config body: {struct.name}")
            config.fields.append(utils.normalize_field(child.text.decode("utf-8")))

        struct.configs.append(config)

    return struct
