from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kconfig.core import structs, utils
from kconfig.utils import ui


app = typer.Typer()


@app.command("find")
def struct_find(
    symbol_name: Annotated[str, typer.Argument(help="Name of the symbol to find.")],
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Find nested structures."),
) -> None:
    """Find a symbol inside the kernel."""
    ui.out_info(f"Finding symbol: {symbol_name}")

    kernel = structs.get_kernel_struct(Path("linux-3.2.63"), symbol_name, recursive=recursive)
    ui.out_info(kernel)


@app.command("compare")
def struct_compare(
    symbol_name: str,
) -> None:
    """Find a symbol inside the kernel."""
    ui.out_info(f"Finding symbol: {symbol_name}")

    kernel = structs.get_kernel_struct(Path("linux-3.2.63"), symbol_name)
    module = structs.get_module_struct(Path("dolos.ko"), symbol_name)

    compare = structs.compare_structure(kernel, module)
    utils.print_struct_comparison(compare)
