from __future__ import annotations

import typer
from rich.syntax import Syntax

from kconfig.core import structs, utils
from kconfig.core_api import get_kernel_struct
from kconfig.styling_api import render_call, render_struct, ui
from kconfig.utils import KconfigSymbolNotFoundError, state

from .options import KernelOpt, ModuleOpt, RecursiveOpt, SymbolOpt  # noqa: TC001


app = typer.Typer()


@app.command("find")
def struct_find(kernel: KernelOpt, symbol: SymbolOpt, recursive: RecursiveOpt = False) -> None:
    """Find a symbol inside the kernel."""
    state.kernel_version = kernel

    struct = render_call(
        get_kernel_struct,
        f"Starting{' recursive ' if recursive else ' '}extraction for {symbol} ...",
        state.kernel_dir,
        symbol,
        recursive=recursive,
    )
    if not struct:
        raise KconfigSymbolNotFound(state.kernel_version or "Unknown", symbol)

    ui.raw.print(render_struct(struct))
    if recursive:
        ui.out_info(f"Found {kernel_struct.dependencies} dependencies!")


@app.command("body")
def struct_body(kernel: KernelOpt, symbol: SymbolOpt, recursive: RecursiveOpt = False) -> None:
    """Get the body of a structure from the kernel."""
    state.kernel_version = kernel

    struct = render_call(
        get_kernel_struct,
        f"Starting{' recursive ' if recursive else ' '}extraction for {symbol} ...",
        state.kernel_dir,
        symbol,
        recursive=recursive,
    )
    if not struct:
        raise KconfigSymbolNotFound(state.kernel_version or "Unknown", symbol)

    # Print output
    ui.raw.print(render_struct(struct))


@app.command("compare")
def struct_compare(kernel: KernelOpt, modules: ModuleOpt, symbol: SymbolOpt, recursive: RecursiveOpt = False) -> None:
    """Compare a kernel struct's layout against compiled module binaries."""
    state.kernel_version = kernel
    state.module_dir = modules

    kernel_struct = render_call(
        get_kernel_struct,
        f"Starting{' recursive ' if recursive else ' '}extraction for {symbol} ...",
        state.kernel_dir,
        symbol,
        recursive=recursive,
    )
    if not kernel_struct:
        raise KconfigSymbolNotFound(state.kernel_version or "Unknown", symbol)

    structs.get_module_capabilities(state.module_dir)
    report = structs.analyze_struct_tree(kernel_struct, state.module_dir)
    utils.print_struct_comparison(report)
