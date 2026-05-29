from __future__ import annotations

from pathlib import Path

from kconfig.utils.exceptions import KconfigFileError, KconfigQueryImpossibleError
from kconfig.utils.types import KconfigStruct, KconfigStructConfig

from .run_query import run_file_query, run_query
from .utils import get_nodes, get_single_node, get_single_node_text, normalize_field


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
    project_root = Path(__file__).parent.parent
    query_file = project_root / "queries" / "find-struct.scm"
    if not query_file.exists():
        raise KconfigFileError(f"Missing query: {query_file.name}")
    query_str = query_file.read_text().replace("__STRUCT_NAME__", struct_name)

    # Get results from query
    result = run_file_query(file, query_str)
    return KconfigStruct(
        name=get_single_node_text(result, "struct.name"),
        body=get_single_node_text(result, "struct.def"),
    )


def find_struct_configs(struct_code: str) -> list[KconfigStructConfig]:
    """Find configurable options inside a structure.

    Args:
        struct_code (str): Structure to parse.

    Returns:
        list[KconfigStructConfig]: List of Config and field structures.

    """
    project_root = Path(__file__).parent.parent
    query_file = project_root / "queries" / "ifdef-struct.scm"
    if not query_file.exists():
        raise KconfigFileError(f"Missing query: {query_file.name}")
    query = query_file.read_text()

    # Get results from query
    result = run_query(struct_code, query)
    struct_name = get_single_node(result, "struct.name")
    config_names = get_nodes(result, "config.name")
    config_block = get_nodes(result, "config.block")

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
            config.fields.append(normalize_field(child.text.decode("utf-8")))

        configs.append(config)

    return configs
