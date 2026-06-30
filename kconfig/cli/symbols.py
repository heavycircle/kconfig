from __future__ import annotations

import typer

from kconfig.control_api import get_function_signature, kconfig_state
from kconfig.styling_api import ui

from .options import KernelOpt, SymbolOpt  # noqa: TC001

app = typer.Typer()


@app.command("find")
def symbol_find(kernel: KernelOpt, symbol: SymbolOpt) -> None:
    """Find a symbol inside the kernel."""
    kconfig_state.kernel_version = kernel

    ui.out_info(f"Finding symbol: {symbol}")
    signature = get_function_signature(kconfig_state.kernel_dir, symbol)
    ui.out_info(f"Signature: {signature}")
