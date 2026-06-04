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
    console.print(Panel(f"Analysis for [bold]struct {struct_name}[/bold]"))

    config_table = Table(title="KConfig Status", show_header=True, header_style="bold magenta")
    config_table.add_column("CONFIG Flag")
    config_table.add_column("State", justify="center")

    for cfg in result.enabled_configs:
        config_table.add_row(cfg, "[bold green]ENABLED[/bold green]")
    for cfg in result.disabled_configs:
        config_table.add_row(cfg, "[bold red]DISABLED[/bold red]")
    for cfg in result.conflicts:
        config_table.add_row(cfg, "[bold red]DISABLED[/bold red]")

    console.print(config_table)
