from __future__ import annotations

from kconfig.core import parser, utils
from kconfig.utils import (
    KconfigAnalysisInvalidError,
    KconfigStruct,
    KconfigStructComparison,
    KconfigStructConfig,
    ui,
)


def get_struct_configs(struct: KconfigStruct) -> KconfigStruct:
    """Get a structure's source code from the kernel.

    Args:
        struct (KconfigStruct): Base struct information.

    Returns:
        KconfigStruct: Complete struct information with config values.

    """
    query = parser.get_query("struct-config")
    matches = parser.run_query(utils.sanitize_kernel_macros(struct.body), query)
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

        struct.configs.append(config)

    return struct


def compare_structure(kernel_struct: KconfigStruct, module_struct: KconfigStruct) -> KconfigStructComparison:
    """Compare a kernel structure against a compiled module's target.

    Args:
        kernel_struct (KconfigStruct): Kernel structure (with explicit configs).
        module_struct (KconfigStruct): Module structur (comparison).

    Raises:
        KconfigAnalysisInvalidError: Attempting to compare different structures.

    Reurns:
        KconfigStructComparison: Comparison object for this structur.

    """
    if kernel_struct.name != module_struct.name:
        raise KconfigAnalysisInvalidError(f"Comparing different structs: {kernel_struct.name} and {module_struct.name}")

    module_fields = utils.get_struct_members(module_struct)
    result = KconfigStructComparison(name=kernel_struct.name)

    # Compare the kernel_struct to this fields list
    ui.out_info(f"Checking {len(kernel_struct.configs)} config guards ...")
    for config in kernel_struct.configs:
        ui.out_debug(f" >> Checking configs: '{config.name}'")

        config_enabled = True
        for field_name, field_type in config.fields.items():
            ui.out_debug(f" >> >> Checking field: '{field_name}'")

            # Check field name
            if field_name not in module_fields:
                ui.out_debug(f" >> >> Config disabled: missing {field_name}")
                config_enabled = False
                break

            # Compare field type
            kernel_type = utils.normalize_type(field_type)
            module_type = utils.normalize_type(module_fields.get(field_name, ""))
            if kernel_type != module_type:
                ui.out_debug(f" >> >> >> Type mismatch: '{kernel_type}' vs '{module_type}'")
                result.type_mismatches.add(config.name)

        if config_enabled:
            ui.out_debug(f" >> {config.name}: Enabled!")
            result.enabled_configs.add(config.name)
        else:
            ui.out_debug(f" >> {config.name}: Disabled!")
            result.disabled_configs.add(config.name)

    return result


def get_custom_struct_members(struct_code: bytes) -> tuple[set[bytes], ...]:
    """Get custom struct members."""
    structs, unions, typedefs = set[bytes](), set[bytes](), set[bytes]()
    for _, captures in parser.run_query(struct_code, parser.get_query("signature-match")):
        structs.update(utils.get_node_text(n) for n in captures.get("struct.name", []))
        unions.update(utils.get_node_text(n) for n in captures.get("union.name", []))
        typedefs.update(utils.get_node_text(n) for n in captures.get("typedef.name", []))

    typedefs = typedefs - structs - unions
    return structs, unions, typedefs
