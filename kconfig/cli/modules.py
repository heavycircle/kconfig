from __future__ import annotations

import typer

from kconfig.control_api import kconfig_state, probe_all_modules
from kconfig.styling_api import render_module_capabilities_table

from .options import ModuleOpt  # noqa: TC001

app = typer.Typer()


@app.command("info")
def module_info(modules: ModuleOpt) -> None:
    """Report each module/vmlinux file's BTF/DWARF/vermagic introspection capabilities.

    Useful before ``struct analyze``/``signature analyze`` to see up front
    which modules get full struct-layout comparison and which fall back to a
    degraded tier (or nothing at all) -- the same probe those commands
    already run internally when building their module cache.
    """
    kconfig_state.module_dir = modules
    render_module_capabilities_table(probe_all_modules(kconfig_state.module_dir))
