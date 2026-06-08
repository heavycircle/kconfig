from __future__ import annotations

from pathlib import Path

import typer

from kconfig.control_api import get_kernel_struct
from kconfig.styling_api import ui


app = typer.Typer()


@app.command("find")
def config_find(symbol_name: str) -> None:
    """Find a symbol inside the kernel."""
    ui.out_info(f"Finding symbol: {symbol_name}")

    signature = get_kernel_struct(Path("linux-3.2.63"), symbol_name)
    ui.out_info(f"Signature: {signature}")
