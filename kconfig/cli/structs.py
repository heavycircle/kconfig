from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kconfig.core import structs, utils
from kconfig.utils import KconfigSymbolNotFoundError, ui


app = typer.Typer()


@app.command("find")
def struct_find(
    symbol_name: Annotated[str, typer.Argument(help="Name of the symbol to find.")],
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Find nested structures."),
) -> None:
    """Find a symbol inside the kernel."""
    ui.out_info(f"Finding symbol: {symbol_name}")

    struct = structs.get_kernel_struct(Path("linux-3.2.63"), symbol_name, recursive=recursive)
    if not struct:
        raise KconfigSymbolNotFoundError(symbol_name, "linux-3.2.63")

    ui.out_info(struct)
    if recursive:
        ui.out_info(f"Found {struct.nested_count} dependencies!")


@app.command("compare")
def struct_compare(
    symbol_name: Annotated[str, typer.Argument(help="Name of the symbol to compare.")],
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Find nested structures."),
) -> None:
    """Find a symbol inside the kernel."""
    ui.out_info(f"Finding symbol: {symbol_name}")

    kernel = structs.get_kernel_struct(Path("linux-3.2.63"), symbol_name, recursive=recursive)
    if not kernel:
        raise KconfigSymbolNotFoundError(symbol_name, "linux-3.2.63")

    structs.get_module_capabilities(Path("modules"))
    report = structs.analyze_struct_tree(kernel)
    utils.print_struct_comparison(symbol_name, report)
