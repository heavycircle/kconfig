from __future__ import annotations

import typer

from kconfig.control_api import (
    analyze_structs,
    build_module_location_cache,
    build_struct_location_cache,
    build_typedef_location_cache,
    gather_struct_guards,
    get_function_signature,
    get_signature_structs,
    kconfig_state,
)
from kconfig.styling_api import render_member_guards, render_signature, ui

from .options import ArchOpt, ConfigOpt, KernelOpt, ModuleOpt, OutputFormat, OutputOpt, RecursiveOpt, SymbolOpt

app = typer.Typer()


def _signature_members(symbol: str) -> list[str]:
    """Find a signature's struct/union members, sorted for stable output.

    Typedef members are intentionally excluded -- they don't carry their own
    field list to check presence/guards on, unlike a struct/union tag name.
    """
    signature = get_function_signature(kconfig_state.kernel_dir, symbol)
    return sorted(signature.members.structs | signature.members.unions)


@app.command("find")
def signature_find(kernel: KernelOpt, symbol: SymbolOpt) -> None:
    """Find a function or macro signature and report its custom struct/union/typedef members."""
    kconfig_state.kernel_version = kernel

    ui.out_info(f"Finding signature: {symbol}")
    signature = get_function_signature(kconfig_state.kernel_dir, symbol)
    render_signature(signature)


@app.command("configs")
def signature_configs(
    kernel: KernelOpt, symbol: SymbolOpt, recursive: RecursiveOpt = False, arch: ArchOpt = "x86"
) -> None:
    """Report the CONFIG guards found inside a signature's custom struct/union members."""
    kconfig_state.kernel_version = kernel
    kconfig_state.arch = arch

    ui.out_info(f"Finding signature: {symbol}")
    members = _signature_members(symbol)
    if not members:
        ui.out_info(f"'{symbol}' has no custom struct/union members.")
        return

    build_struct_location_cache()
    roots = get_signature_structs(members, recursive=recursive)

    guards = [g for name, struct in roots.items() for g in gather_struct_guards(name, struct)]
    render_member_guards(symbol, guards)


@app.command("analyze")
def signature_analyze(  # noqa: PLR0913
    kernel: KernelOpt,
    modules: ModuleOpt,
    symbol: SymbolOpt,
    current: ConfigOpt = None,
    recursive: RecursiveOpt = False,
    output: OutputOpt = OutputFormat.table,
    arch: ArchOpt = "x86",
) -> None:
    """Compare a signature's custom struct/union members against compiled module binaries."""
    kconfig_state.kernel_version = kernel
    kconfig_state.module_dir = modules
    kconfig_state.arch = arch

    if output is not OutputFormat.json:
        ui.out_info(f"Finding signature: {symbol}")
    members = _signature_members(symbol)
    if not members:
        ui.out_info(f"'{symbol}' has no custom struct/union members.")
        return

    build_struct_location_cache()
    if output is not OutputFormat.json:
        ui.out_info(f"Building{' recursive ' if recursive else ' '}layout: '{symbol}' ({', '.join(members)})")
    roots = get_signature_structs(members, recursive=recursive)
    if not roots:
        ui.out_info(f"None of '{symbol}''s custom members could be resolved.")
        return

    build_module_location_cache()
    build_typedef_location_cache()
    if output is not OutputFormat.json:
        ui.out_info(f"Analyzing CONFIG Options: '{symbol}'")
    analyze_structs(roots, current=current, output_format=output.value)
