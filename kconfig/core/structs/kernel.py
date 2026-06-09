from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser, utils
from kconfig.core.config import state
from kconfig.exceptions import KconfigSymbolNotFoundError
from kconfig.styling_api import ui
from kconfig.types import KconfigStruct, KconfigStructField


if TYPE_CHECKING:
    from pathlib import Path

    from rich.status import Status
    from tree_sitter import Node


def find_struct_declaration(kernel_root: Path, struct_name: str) -> tuple[Node, Path, str]:
    """Find the declaration of a structure inside the kernel directory.

    Args:
        kernel_root (Path): The kernel root to search for.
        struct_name (str): Name of the structure to find.

    Raises:
        KconfigSymbolNotFoundError: Struct not found in any candidate file.

    Returns:
        tuple[Node, Path, str]: The struct's AST node, the file it was found in,
            and the resolved struct name (may differ when following typedef aliases).

    """
    for file in utils.find_candidate_struct_files(kernel_root, struct_name):
        contents = file.read_bytes()
        for _, captures in parser.run_query("struct-list", contents):
            struct_names = utils.get_capture_text(captures, "struct.name")
            if not struct_names:
                continue

            found_name = struct_names[0].decode()
            if found_name == struct_name:
                ui.out_debug(f"Found struct {struct_name} in {file} ...")
                return captures["struct.name"][0].parent, file, found_name

    ui.out_debug(f"Cannot find '{struct_name}', searching for aliases ...")
    for file in utils.find_candidate_struct_files(kernel_root, struct_name):
        contents = file.read_bytes()
        for _, captures in parser.run_query("alias-find", contents):
            alias_names = utils.get_capture_text(captures, "alias.name")
            if not alias_names:
                continue

            found_alias = alias_names[0].decode()
            if found_alias == struct_name:
                true_name = utils.get_capture_text(captures, "alias.target")[0].decode()
                ui.out_debug(f"Resolved alias: {struct_name} -> {true_name}")
                return find_struct_declaration(kernel_root, true_name)

    raise KconfigSymbolNotFoundError(struct_name, kernel_root)


def get_kernel_struct(
    kernel_root: Path,
    struct_name: str,
    recursive: bool = False,
    visited: set[str] | None = None,
    status: Status | None = None,
) -> KconfigStruct | None:
    """Get a structure's configuration from the kernel.

    Args:
        kernel_root (Path): The kernel root to search for.
        struct_name (str): Name of the structure to find.
        recursive (bool): True to search for recursive definitions.
            Can be intense, so defaults to False.
        visited (set[str] | None): Recursive node track.
        status (Status | None): Status output for the terminal.

    Returns:
        KconfigStruct | None: Structure information including fields and config guards,
            or ``None`` if the struct was already visited (cycle detected).

    """
    if visited is None:
        visited = set()

    if struct_name in visited:
        return None
    visited.add(struct_name)

    if status:
        status.update(f"Parsed {len(visited)} structs ... (Analyzing: [bold cyan]{struct_name}[/bold cyan])")

    node, path, name = find_struct_declaration(kernel_root, struct_name)
    struct_layout = KconfigStruct(name=name, file=path.relative_to(state.kernel_dir))

    # Get the fields inside this struct
    captures = parser.run_node_query(node, "struct-fields")
    if "field.def" not in captures:
        ui.out_warning(f"Struct '{name}' has no fields.")
        return struct_layout

    # Check for fields enclosing configs
    for i, field_node in enumerate(captures["field.def"]):
        if not parser.is_direct_member(field_node, node):
            continue

        name_node = captures["field.name"][i]
        field_name = name_node.text.decode()
        field_type = captures["field.type"][i].text.decode()
        true_type = parser.get_true_type(name_node, field_type)

        config_chain = parser.get_enclosing_configs(field_node)
        new_field = KconfigStructField(field_name, true_type, config_chain)
        struct_layout.fields.append(new_field)

    if recursive:
        ui.out_debug(f" >> Checking recursively: {struct_name}")
        members = parser.get_custom_members(node)
        for member in members.structs:
            ui.out_debug(f" >> {struct_name} has recursive member: {member}")

            try:
                nested_struct = get_kernel_struct(
                    kernel_root,
                    member,
                    recursive=True,
                    visited=visited,
                    status=status,
                )
                if nested_struct:
                    struct_layout.nested.append(nested_struct)
            except KconfigSymbolNotFoundError as e:
                ui.out_debug(f"Could not find nested struct: '{member}': {e}")

    return struct_layout
