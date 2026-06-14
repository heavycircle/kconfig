from __future__ import annotations

import typer

from kconfig.control_api import build_kernel_cache, get_symbol_typedef, state
from kconfig.styling_api import render_field_type_table, ui

from .options import KernelOpt, SymbolOpt  # noqa: TC001


app = typer.Typer()


@app.command("find")
def type_find(symbol: SymbolOpt, kernel: KernelOpt) -> None:
    """Find a type definition inside the kernel."""
    state.kernel_version = kernel

    build_kernel_cache()
    typedefs = get_symbol_typedef(symbol)
    render_field_type_table(typedefs)
