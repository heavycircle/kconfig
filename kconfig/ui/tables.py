from __future__ import annotations

from typing import TYPE_CHECKING

import sympy
from rich.table import Table

from .logging import ui

if TYPE_CHECKING:
    from pathlib import Path

    from kconfig.core.cache.distro_kernel import DistroSourcePackage
    from kconfig.types import KconfigFieldType, KconfigMemberGuard, KconfigModuleCapabilities


def render_distro_package_table(packages: list[DistroSourcePackage]) -> None:
    """Render available distro kernel source package versions as a Rich table.

    Args:
        packages (list[DistroSourcePackage]): Versions to display, e.g. from
            ``list_source_packages``. Each row also shows the kernel ABI
            name(s) (``uname -r`` style) that version's ``linux-image-*``
            binaries produce, to bridge a known running kernel back to the
            source version needed to fetch it.

    """
    if not packages:
        ui.out_info("No package versions found.")
        return

    table = Table(show_header=True, header_style="bold cyan", border_style="cyan")
    table.add_column("Version", style="bold white")
    table.add_column("Kernel ABI(s)", style="yellow")

    for pkg in packages:
        table.add_row(pkg.version, ", ".join(pkg.image_abis) if pkg.image_abis else "-")

    ui.raw.print(table)


def render_distro_search_table(results: list[tuple[str, DistroSourcePackage]]) -> None:
    """Render matches from a cross-release kernel version search as a Rich table.

    Args:
        results (list[tuple[str, DistroSourcePackage]]): ``(release, package)``
            pairs, e.g. from searching every known release for a kernel
            version -- for when you don't yet know which release a kernel
            build belongs to.

    """
    if not results:
        ui.out_info("No matching kernel versions found in any release.")
        return

    table = Table(show_header=True, header_style="bold cyan", border_style="cyan")
    table.add_column("Release", style="bold white")
    table.add_column("Version", style="bold white")
    table.add_column("Kernel ABI(s)", style="yellow")

    for release, pkg in results:
        table.add_row(release, pkg.version, ", ".join(pkg.image_abis) if pkg.image_abis else "-")

    ui.raw.print(table)


def render_kernel_version_table(versions: list[str], kernel_dir: Path) -> None:
    """Render the list of cached kernel versions as a Rich table to the terminal.

    Args:
        versions (list[str]): Sorted list of kernel version strings (e.g. ``["6.1.0", "5.15.0"]``).
        kernel_dir (Path): Base directory where kernels are stored, used to display local paths.

    """
    if not versions:
        ui.out_info("No kernels currently cached.")
        ui.out_info("Use 'kconfig kernel fetch <version>' to download one.")
        return

    table = Table(show_header=True, header_style="bold cyan", border_style="cyan")
    table.add_column("Kernel Version", style="bold white")
    table.add_column("Local Patch", style="dim")

    for version in versions:
        table.add_row(version, str(kernel_dir / f"linux-{version}"))

    ui.raw.print(table)


def render_field_type_table(field: KconfigFieldType) -> None:
    """Render a KconfigFieldType as a table."""
    if not field.resolved_types:
        ui.out_info(f"No resolved types: '{field.original_type}'")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Original Type", justify="right", style="cyan")
    table.add_column("Resolved Type", justify="left")
    table.add_column("File", style="dim")
    table.add_column("CONFIG Options", style="yellow")

    for f in sorted(field.resolved_types, key=lambda i: (i.resolved_type, i.file)):
        guard_str = "" if f.guard is sympy.true else str(f.guard)
        table.add_row(field.original_type, f.resolved_type, str(f.file), guard_str)

    ui.raw.print(table)


def render_member_guards(symbol: str, guards: list[KconfigMemberGuard]) -> None:
    """Render the CONFIG guards found inside a signature's custom members as a Rich table.

    Args:
        symbol (str): Name of the function/macro the members were reached
            from, used only for the message when no guards are found.
        guards (list[KconfigMemberGuard]): Guards found, e.g. from ``gather_struct_guards``.

    """
    if not guards:
        ui.out_info(f"No CONFIG guards found in '{symbol}''s custom members.")
        return

    table = Table(show_header=True, header_style="bold cyan", border_style="cyan")
    table.add_column("Member", style="bold white")
    table.add_column("Struct", style="cyan")
    table.add_column("Field", style="white")
    table.add_column("CONFIG Guard", style="yellow")

    for g in sorted(guards, key=lambda i: (i.member, i.struct_name, i.field_name)):
        table.add_row(g.member, g.struct_name, g.field_name, str(g.guard))

    ui.raw.print(table)


def render_module_capabilities_table(capabilities: list[KconfigModuleCapabilities]) -> None:
    """Render each module/vmlinux file's introspection capabilities as a Rich table.

    Args:
        capabilities (list[KconfigModuleCapabilities]): Per-file results, e.g.
            from ``probe_all_modules`` -- surfaces which files will get full
            struct-layout comparison in ``struct analyze``/``signature
            analyze`` versus a degraded (or unusable) fallback tier, before
            either command is actually run.

    """
    if not capabilities:
        ui.out_info("No .ko or vmlinux files found.")
        return

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        caption=(
            "Tiers, best to worst: full (BTF/DWARF layout) > split-btf (needs --btf_base) "
            "> vermagic-only (no layout, vermagic readable) > none (nothing usable). "
            "Only full/split-btf feed struct-layout evidence into analysis today."
        ),
        caption_style="dim",
    )
    table.add_column("File", style="bold white")
    table.add_column("Tier", style="yellow")
    table.add_column("DWARF", style="cyan")
    table.add_column("BTF", style="cyan")
    table.add_column("Symtab", style="cyan")
    table.add_column("Vermagic", style="dim")

    for c in sorted(capabilities, key=lambda i: i.file.name):
        table.add_row(
            c.file.name,
            c.tier,
            "yes" if c.has_dwarf else "no",
            "yes" if c.has_btf else "no",
            "stripped" if c.symtab_stripped else "yes",
            c.vermagic or "-",
        )

    ui.raw.print(table)


def render_config_diff_table(current_config: dict[str, bool], computed_config: dict[str, bool]) -> None:
    """Render the difference in the computed config versus a current config.

    Args:
        current_config (dict[str, bool]): The current config.
            Probably computed by parse_config_file.
        computed_config (dict[str, bool]): The computed config.
            Probably computed by analyze_struct_tree.

    """
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("CONFIG Option", style="cyan")
    table.add_column("Status")
    table.add_column("Notes", style="dim")

    for config, is_set in computed_config.items():
        config_str = str(config)
        if not config_str.startswith("CONFIG_"):
            continue

        computed_set = current_config.get(config_str, False)
        if is_set == computed_set:
            continue

        enable_str = "[bold green]Enabled[/]" if is_set else "[bold red]Disabled[/]"
        reason_str = "Incorrect" if config_str in current_config else "Missing"
        table.add_row(config_str, enable_str, f"{reason_str} in current .config")

    ui.raw.print(table)
