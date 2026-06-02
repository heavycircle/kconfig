from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


if TYPE_CHECKING:
    from kconfig.utils import KconfigStructComparison

console = Console()

def print_struct_comparison(result: StructComparisonResult) -> None:
    """Render the comparison result to the terminal."""
    color = "green" if result.is_perfect_match else "red"
    console.print(Panel(f"Analysis for [bold]{result.struct_name}[/bold] in {result.module_path}", border_style=color))

    config_table = Table(title="KConfig Status", show_header=True, header_style="bold magenta")
    config_table.add_column("Config Flag")
    config_table.add_column("State", justify="center")

    for cfg in result.enabled_configs:
        config_table.add_row(cfg, "[bold green]ENABLED[/bold green]")
    for cfg in result.disabled_configs:
        config_table.add_row(cfg, "[bold red]DISABLED[/bold red]")
        
    console.print(config_table)

    if result.order_mismatches:
        console.print("\n[bold yellow]Order Mismatches:[/bold yellow]")
        for issue in result.order_mismatches:
            console.print(f"  - {issue}")

    if result.type_mismatches:
        console.print("\n[bold red]Type Mismatches:[/bold red]")
        for issue in result.type_mismatches:
            console.print(f"  - {issue}")
            
    console.print("\n")
