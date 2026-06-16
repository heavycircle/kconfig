from __future__ import annotations

from typing import Annotated

from typer import Argument, Option

ConfigOpt = Annotated[
    str | None,
    Option("-c", "--current", help="Current .config. Only reports incorrect settings."),
]

KernelOpt = Annotated[
    str | None,
    Option("-k", "--kernel", help="Target kernel version (defaults to host kernel)."),
]

ModuleOpt = Annotated[
    str | None,
    Option("-m", "--modules", help="Path to reference kernel module(s)"),
]

RecursiveOpt = Annotated[
    bool,
    Option("-r", "--recursive", help="Recursive search for nested structures."),
]

SymbolOpt = Annotated[
    str,
    Argument(help="Name of the symbol to find."),
]
