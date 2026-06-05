from __future__ import annotations

import typer
from rich.syntax import Syntax

from kconfig.core import structs, utils
from kconfig.utils import KconfigSymbolNotFoundError, state, ui

from .options import KernelOpt, ModuleOpt, RecursiveOpt, SymbolOpt  # noqa: TC001

app = typer.Typer()


@app.command("find")
def struct_find(kernel: KernelOpt, symbol: SymbolOpt, recursive: RecursiveOpt) -> None:
    """Find a symbol inside the kernel."""
    state.kernel_version = kernel

    with ui.raw.status(f"Starting{' recursive ' if recursive else ' '}extraction for {symbol} ...") as status:
        kernel_struct = structs.get_kernel_struct(state.kernel_dir, symbol, recursive=recursive, status=status)
        if not kernel_struct:
            raise KconfigSymbolNotFoundError(symbol_name, state.kernel_version or "Unknown")

        ui.out_info(struct)
        if recursive:
            ui.out_info(f"Found {struct.nested_count} dependencies!")


@app.command("body")
def struct_body(kernel: KernelOpt, symbol: SymbolOpt) -> None:
    """Get the body of a structure from the kernel."""
    state.kernel_version = kernel

    kernel_struct = structs.get_kernel_struct(state.kernel_dir, symbol, recursive=recursive, status=status)
    if not kernel_struct:
        raise KconfigSymbolNotFoundError(symbol_name, state.kernel_version or "Unknown")

    ui.raw.print(Syntax(kernel_struct.body.decode(), "c", theme="ansi_dark", line_numbers=True))


@app.command("compare")
def struct_compare(kernel: KernelOpt, modules: ModuleOpt, symbol: SymbolOpt, recursive: RecursiveOpt) -> None:
    """Find a symbol inside the kernel."""
    state.kernel_version = kernel
    state.module_dir = modules

    with ui.raw.status(f"Starting{' recursive ' if recursive else ' '}extraction for {symbol} ...") as status:
        kernel_struct = structs.get_kernel_struct(state.kernel_dir, symbol, recursive=recursive, status=status)
        if not kernel_struct:
            raise KconfigSymbolNotFoundError(symbol_name, state.kernel_version or "Unknown")

    structs.get_module_capabilities(state.module_dir)
    report = structs.analyze_struct_tree(kernel_struct, state.module_dir)
    utils.print_struct_comparison(report)
