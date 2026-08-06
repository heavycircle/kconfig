from __future__ import annotations

import typer

from kconfig.control_api import (
    analyze_struct_tree,
    build_module_location_cache,
    build_struct_location_cache,
    build_typedef_location_cache,
    get_kernel_struct,
    kconfig_state,
)
from kconfig.styling_api import render_struct, ui

from .options import ConfigOpt, KernelOpt, ModuleOpt, OutputFormat, OutputOpt, RecursiveOpt, SymbolOpt

app = typer.Typer()


@app.command("find")
def struct_find(kernel: KernelOpt, symbol: SymbolOpt, recursive: RecursiveOpt = False) -> None:
    """Find a symbol inside the kernel."""
    kconfig_state.kernel_version = kernel

    build_struct_location_cache()
    struct = get_kernel_struct(symbol, recursive=recursive)

    ui.out_info(f"Rendering struct: {symbol}")
    render_struct(struct)


@app.command("analyze")
def struct_analyze(  # noqa: PLR0913
    kernel: KernelOpt,
    modules: ModuleOpt,
    symbol: SymbolOpt,
    current: ConfigOpt = None,
    recursive: RecursiveOpt = False,
    output: OutputOpt = OutputFormat.table,
) -> None:
    """Compare a kernel struct's layout against compiled module binaries."""
    kconfig_state.kernel_version = kernel
    kconfig_state.module_dir = modules

    build_struct_location_cache()
    if output is not OutputFormat.json:
        ui.out_info(f"Building{' recursive ' if recursive else ' '}layout: '{symbol}'")
    kernel_struct = get_kernel_struct(symbol, recursive=recursive)

    build_module_location_cache()
    build_typedef_location_cache()
    if output is not OutputFormat.json:
        ui.out_info(f"Analyzing CONFIG Options: '{symbol}'")
    analyze_struct_tree(kernel_struct, current=current, output_format=output.value)
