from __future__ import annotations

import typer

from kconfig.control_api import build_typedef_location_cache, kconfig_state, resolve_typedef
from kconfig.styling_api import render_field_type_table
from kconfig.types import KconfigFieldType

from .options import KernelOpt, SymbolOpt  # noqa: TC001

app = typer.Typer()


@app.command("find")
def type_find(symbol: SymbolOpt, kernel: KernelOpt) -> None:
    """Find a type definition inside the kernel."""
    kconfig_state.kernel_version = kernel

    build_typedef_location_cache()
    resolved = resolve_typedef(symbol)
    render_field_type_table(KconfigFieldType(symbol, resolved_types=resolved))
