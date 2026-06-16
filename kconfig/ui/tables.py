from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from .logging import ui


if TYPE_CHECKING:
    from pathlib import Path

    from kconfig.types import KconfigFieldType


def render_kernel_version_table(versions: list[str], kernel_dir: Path) -> None:
    """Render the list of cached kernel versions as a Rich table to the terminal.

    Args:
        versions (list[str]): Sorted list of kernel version strings (e.g. ``["6.1.0", "5.15.0"]``).
        kernel_dir (Path): Base directory where kernels are stored, used to display local paths.

    """
    if not versions:
        ui.out_info("No kernels currently cached.")
        ui.out_info("Use 'kconfig kernel fetch <version>' to download one.")
        return

    table = Table(show_header=True, header_style="bold cyan", border_style="cyan")
    table.add_column("Kernel Version", style="bold white")
    table.add_column("Local Patch", style="dim")

    for version in versions:
        table.add_row(version, str(kernel_dir / f"linux-{version}"))


def render_field_type_table(field: KconfigFieldType) -> None:
    """Render a KconfigFieldType as a table."""
    if not field.resolved_type:
        ui.out_info(f"No resolved types: '{field.original_type}'")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Original Type", justify="right", style="cyan")
    table.add_column("Resolved Type", justify="left")
    table.add_column("File", style="dim")
    table.add_column("CONFIG Options", style="yellow")

    for f in sorted(field.resolved_type, key=lambda i: (i.true_type, i.file)):
        table.add_row(field.original_type, f.true_type, str(f.file), str(f.depends) or "")

    ui.raw.print(table)


def render_config_diff_table(current_config: dict[str, bool], computed_config: dict[str, bool]) -> None:
    """Render the difference in the computed config versus a current config.

    Args:
        current_config (dict[str, bool]): The current config.
            Probably computed by parse_config_file.
        computed_config (dict[str, bool]): The computed config.
            Probably computed by analyze_struct_tree.

    """
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("CONFIG Option", style="cyan")
    table.add_column("Status")
    table.add_column("Notes", style="dim")

    for config, is_set in computed_config.items():
        config_str = str(config)
        if not config_str.startswith("CONFIG_"):
            continue

        computed_set = current_config.get(config_str, False)
        if is_set == computed_set:
            continue

        enable_str = "[bold green]Enabled[/]" if is_set else "[bold red]Disabled[/]"
        reason_str = "Incorrect" if config_str in current_config else "Missing"
        table.add_row(config_str, enable_str, f"{reason_str} in current .config")

    ui.raw.print(table)
