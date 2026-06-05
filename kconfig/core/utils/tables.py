from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


if TYPE_CHECKING:
    from kconfig.utils import KconfigAnalysis

console = Console()


def print_struct_comparison(struct_name: str, result: KconfigAnalysis) -> None:
    """Render the comparison result to the terminal."""
    console.print(Panel(f"Analysis for [bold cyan]struct {struct_name}[/bold cyan]"))

    config_table = Table(title="Resolved KConfig States", show_header=True, header_style="bold magenta")
    config_table.add_column("CONFIG Flag")
    config_table.add_column("State", justify="center")
    config_table.add_column("Primary Evidence")
    config_table.add_column("Matches", justify="center")

    for cfg, matches in result.enabled_configs.items():
        config_table.add_row(cfg, "[bold green]ENABLED[/bold green]", str(matches[0]), str(len(matches)))
    for cfg, matches in result.disabled_configs.items():
        config_table.add_row(cfg, "[dim]DISABLED[/dim]", str(matches[0]), str(len(matches)))
    console.print(config_table)

    if result.conflicts:
        console.print("")

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

        console.print(conflict_table)
