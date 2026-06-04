from __future__ import annotations

from pathlib import Path

import typer

from kconfig.core import symbols
from kconfig.utils import ui


app = typer.Typer()


@app.command("find")
def symbol_find(symbol_name: str) -> None:
    """Find a symbol inside the kernel."""
    ui.out_info(f"Finding symbol: {symbol_name}")

    signature = symbols.get_function_signature(Path("linux-3.2.63"), symbol_name)
    ui.out_info(f"Signature: {signature}")
