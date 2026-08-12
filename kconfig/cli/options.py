from __future__ import annotations

from enum import Enum
from typing import Annotated

from typer import Argument, Option


class OutputFormat(str, Enum):
    """Output format for a command that reports an analysis result."""

    table = "table"
    json = "json"


class DistroVariant(str, Enum):
    """Which distro's patched variant of an upstream kernel version to fetch."""

    debian = "debian"
    ubuntu = "ubuntu"


ArchOpt = Annotated[
    str,
    Option(
        "-a",
        "--arch",
        help="Target architecture (an arch/<name> directory, e.g. x86, arm64) for disambiguating per-arch structs.",
    ),
]

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

OutputOpt = Annotated[
    OutputFormat,
    Option("-o", "--output", help="Output format for the analysis result."),
]

RecursiveOpt = Annotated[
    bool,
    Option("-r", "--recursive", help="Recursive search for nested structures."),
]

SymbolOpt = Annotated[
    str,
    Argument(help="Name of the symbol to find."),
]
