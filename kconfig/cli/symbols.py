from __future__ import annotations

import typer

from kconfig.core import symbols
from kconfig.utils import state, ui

from .options import KernelOpt, SymbolOpt  # noqa: TC001


app = typer.Typer()


@app.command("find")
def symbol_find(kernel: KernelOpt, symbol: SymbolOpt) -> None:
    """Find a symbol inside the kernel."""
    state.kernel_version = kernel

    ui.out_info(f"Finding symbol: {symbol}")
    signature = symbols.get_function_signature(state.kernel_dir, symbol)
    ui.out_info(f"Signature: {signature}")
