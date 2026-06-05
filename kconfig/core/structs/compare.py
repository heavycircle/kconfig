from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kconfig.utils import KconfigAnalysis, KconfigConfigEvidence, KconfigSymbolNotFoundError, ui

from .module import get_module_struct


if TYPE_CHECKING:
    from kconfig.utils import KconfigStruct


# def compare_structure(kernel_struct: KconfigStruct, module_struct: KconfigStruct) -> KconfigStructComparison:
#     """Compare a kernel structure against a compiled module's target.

#     Args:
#         kernel_struct (KconfigStruct): Kernel structure (with explicit configs).
#         module_struct (KconfigStruct): Module structur (comparison).

#     Raises:
#         KconfigAnalysisInvalidError: Attempting to compare different structures.

#     Reurns:
#         KconfigStructComparison: Comparison object for this structur.

#     """
#     if kernel_struct.name != module_struct.name:
#         raise KconfigAnalysisInvalidError(f"Comparing different structs: {kernel_struct.name} and {module_struct.name}")

#     module_fields = utils.get_struct_members(module_struct)
#     result = KconfigStructComparison(name=kernel_struct.name)

#     # Compare the kernel_struct to this fields list
#     ui.out_info(f"Checking {len(kernel_struct.configs)} config guards ...")
#     for config in kernel_struct.configs:
#         ui.out_debug(f" >> Checking configs: '{config.name}'")

#         config_enabled = True
#         for field_name, field_type in config.fields.items():
#             ui.out_debug(f" >> >> Checking field: '{field_name}'")

#             # Check field name
#             if field_name not in module_fields:
#                 ui.out_debug(f" >> >> Config disabled: missing {field_name}")
#                 config_enabled = False
#                 break

#             # Compare field type
#             kernel_type = utils.normalize_type(field_type)
#             module_type = utils.normalize_type(module_fields.get(field_name, ""))
#             if kernel_type != module_type:
#                 ui.out_debug(f" >> >> >> Type mismatch: '{kernel_type}' vs '{module_type}'")
#                 result.type_mismatches.add(config.name)

#         if config_enabled:
#             ui.out_debug(f" >> {config.name}: Enabled!")
#             result.enabled_configs.add(config.name)
#         else:
#             ui.out_debug(f" >> {config.name}: Disabled!")
#             result.disabled_configs.add(config.name)

#     return result


def analyze_struct_tree(root_struct: KconfigStruct, report: KconfigAnalysis | None = None) -> KconfigAnalysis:
    """Analyze a structure tree for config options to enable."""
    if report is None:
        report = KconfigAnalysis()

    try:
        layout = get_module_struct(Path("modules"), root_struct.name)
        for config in root_struct.configs:
            for field_name in config.fields:
                is_present = field_name in layout
                report.add_evidence(config.name, KconfigConfigEvidence(root_struct.name, field_name, is_present))

        # TODO: check for type mismatches

        for nested in root_struct.nested_structs:
            analyze_struct_tree(nested, report)
    except KconfigSymbolNotFoundError as e:
        ui.out_debug(f"Skipping: {e}")

    return report
