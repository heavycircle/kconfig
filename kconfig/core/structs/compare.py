from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import analysis
from kconfig.exceptions import KconfigSymbolNotFoundError
from kconfig.types import KconfigAnalysis
from kconfig.ui import ui

from .module import get_module_struct


if TYPE_CHECKING:
    from pathlib import Path

    from kconfig.types import KconfigStruct


def analyze_struct_tree(
    root_struct: KconfigStruct, modules: Path, report: KconfigAnalysis | None = None
) -> KconfigAnalysis:
    """Recursively compare a kernel struct tree against compiled module layouts.

    For each field in the struct (and its nested structs), records whether the
    field is present in the compiled module and which CONFIG guard covers it.

    Args:
        root_struct (KconfigStruct): Root of the struct dependency tree to analyze.
        modules (Path): Path to the directory containing reference ``.ko`` modules.
        report (KconfigAnalysis | None): Existing report to append to; a new one
            is created if ``None``.

    Returns:
        KconfigAnalysis: Aggregated evidence for all CONFIG options encountered.

    """
    if report is None:
        ui.out_info("Running structure comparison ...")
        report = KconfigAnalysis()

    try:
        layout = get_module_struct(modules, root_struct.name)
        solve = analysis.analyze_struct_fields(root_struct.fields, layout)

        # TODO: check for type mismatches
        for nested in root_struct.nested:
            analyze_struct_tree(nested, modules, report)
    except KconfigSymbolNotFoundError as e:
        ui.out_debug(f"Skipping: {e}")

    return report
