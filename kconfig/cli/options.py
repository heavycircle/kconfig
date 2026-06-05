from __future__ import annotations

from typing import Annotated

from typer import Argument, Option

KernelOpt = Annotated[
    str | None,
    Option("-k", "--kernel", help="Target kernel version (defaults to host kernel)."),
]

ModuleOpt = Annotated[
    str | None,
    Option("-m", "--modules", help="Path to reference kernel module(s)"),
]

SymbolOpt = Annotated[
    str,
    Argument(help="Name of the symbol to find."),
]

RecursiveOpt = Annotated[
    bool,
    Option("-r", "--recursive", help="Recursive search for nested structures."),
]
