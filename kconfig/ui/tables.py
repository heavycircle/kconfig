from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from .logging import ui


if TYPE_CHECKING:
    from pathlib import Path

    from kconfig.types import KconfigAnalysis


def render_struct_comparison_table(result: KconfigAnalysis) -> None:
    """Render the struct comparison result as Rich tables to the terminal.

    Args:
        result (KconfigAnalysis): Aggregated analysis containing enabled, disabled,
            and conflicting CONFIG evidence.

    """
    config_table = Table(show_header=True, header_style="bold magenta")
    config_table.add_column("CONFIG Option")
    config_table.add_column("State", justify="center")
    config_table.add_column("Primary Evidence")
    config_table.add_column("Matches", justify="center")

    for cfg, matches in result.enabled_configs.items():
        config_table.add_row(cfg, "[bold green]ENABLED[/bold green]", str(matches[0]), str(len(matches)))
    for cfg, matches in result.disabled_configs.items():
        config_table.add_row(cfg, "[dim]DISABLED[/dim]", str(matches[0]), str(len(matches)))

    ui.raw.print(config_table)

    if result.conflicts:
        ui.raw.print("")

        conflict_table = Table(
            title="[bold red]CONFLICTS DETECTED[/bold red]",
            show_header=True,
            header_style="bold red",
            border_style="red",
        )
        conflict_table.add_column("CONFIG Flag", style="bold yellow")
        conflict_table.add_column("Contradictory Evidence")

        for cfg, evidence_list in result.conflicts.items():
            evidence_strings: list[str] = []
            for ev in evidence_list:
                color = "green" if ev.is_enabled else "red"
                evidence_strings.append(f"[{color}]{ev}[/{color}]")

            combined_evidence = "\n".join(evidence_strings)
            conflict_table.add_row(cfg, combined_evidence)

        ui.raw.print(conflict_table)


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
