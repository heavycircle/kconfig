from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from kconfig.utils import ui


if TYPE_CHECKING:
    from pathlib import Path

    from kconfig.utils import KconfigAnalysis


def print_struct_comparison(result: KconfigAnalysis) -> None:
    """Render the comparison result to the terminal."""
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


def print_kernel_versions(versions: list[str], kernel_dir: Path) -> None:
    """Render the list of kernel versiosn."""
    if not versions:
        ui.out_info(f"No kernels currently cached.")
        ui.out_info(f"Use 'kconfig kernel fetch <version>' to download one.")
        return

    table = Table(show_header=True, header_style="bold cyan", border_style="cyan")
    table.add_column("Kernel Version", style="bold white")
    table.add_column("Local Patch", style="dim")

    for version in version:
        table.add_row(version, str(kernel_dir / f"linux-{version}"))
