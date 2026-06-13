from __future__ import annotations

import typer

from kconfig.control_api import analyze_struct_tree, build_module_struct_cache, get_kernel_struct, state
from kconfig.core.cache import build_kernel_cache
from kconfig.exceptions import KconfigSymbolNotFoundError
from kconfig.styling_api import render_struct, ui

from .options import KernelOpt, ModuleOpt, RecursiveOpt, SymbolOpt  # noqa: TC001


app = typer.Typer()


@app.command("find")
def struct_find(kernel: KernelOpt, symbol: SymbolOpt, recursive: RecursiveOpt = False) -> None:
    """Find a symbol inside the kernel."""
    state.kernel_version = kernel

    build_kernel_cache()
    struct = get_kernel_struct(symbol, recursive=recursive)
    if not struct:
        raise KconfigSymbolNotFoundError(symbol, state.kernel_dir.name)

    ui.out_info(f"Rendering struct: {symbol}")
    ui.raw.print(render_struct(struct))
    if recursive:
        ui.out_info(f"Found {struct.dependencies} dependencies!")


@app.command("compare")
def struct_compare(kernel: KernelOpt, modules: ModuleOpt, symbol: SymbolOpt, recursive: RecursiveOpt = False) -> None:
    """Compare a kernel struct's layout against compiled module binaries."""
    state.kernel_version = kernel
    state.module_dir = modules

    build_kernel_cache()
    kernel_struct = get_kernel_struct(symbol, recursive=recursive)
    if not kernel_struct:
        raise KconfigSymbolNotFoundError(symbol, state.kernel_dir.name)

    build_module_struct_cache()
    analyze_struct_tree(kernel_struct)
