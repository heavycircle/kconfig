from __future__ import annotations

from typing import TYPE_CHECKING

import sympy
from rich.table import Table

from kconfig.core import structs
from kconfig.exceptions import KconfigSymbolNotFoundError
from kconfig.types import KconfigConfigEvidence
from kconfig.ui import ui

from .guards import parse_config_guard

if TYPE_CHECKING:
    from pathlib import Path

    from kconfig.types import KconfigStruct


EVALUATION_CACHE: dict[str, list[KconfigEvidence]] = {}

def gather_evidence(
    struct: KconfigStruct, 
    modules: Path, 
    active_chain: set[str] | None = None
) -> list[KconfigEvidence]:
    if active_chain is None:
        active_chain = set()

    # Check for cache hits
    name = struct.original_name
    if name and name in active_chain:
        return []
    if name and name in _EVIDENCE_CACHE:
        return EVALUATION_CACHE[name]
    if name:
        active_chain.add(name)

    try:
        layout = structs.get_module_struct(modules, name) if name else {}
    except KconfigSymbolNotFoundError:
        ui.out_warning(f"Cannot find struct: '{struct.original_name}'")
        return []

    # Parse fields for config options
    evidence_list: list[KconfigEvidence] = []
    for field in struct.fields:
        if field.depends:
            raw_expr = parse_guard(str(field.depends))
            is_present = field.field_name in layout
            applied = raw_expr if is_present else sympy.Not(raw_expr)
            
            evidence_list.append(
                KconfigEvidence(name or "anonymous", field.field_name, is_present, raw_expr, applied)
            )

        # Make recursive calls
        if field.field_type.layout:
            evidence_list.extend(gather_evidence(field.field_type.layout, modules, active_chain))

    if name:
        active_chain.remove(name)
        EVALUATION_CACHE[name] = evidence_list

    return evidence_list


def analyze_struct_tree(root_struct: KconfigStruct, modules: Path) -> None:
    evidence = gather_struct_evidence(root_struct, modules)
    if not evidence:
        ui.out_info(f"No CONFIG guards found in {root_struct.original_name}")
        return

    constraints = {}
    for ev in evidence:
        constraints.setdefault(ev.constraints, []).append(ev)

    global_state = sympy.true
    global_conflict = False

    table = Table(title=f"Configuration Analysis: {root_struct.original_name}")
    table.add_column("Required Config", style="magenta", justify="right")
    table.add_column("State", justify="center")
    table.add_column("Evidence", style="white")

    for con, ev in constraints.items():
        ev_str = "\n".join(f" - {e}" for e in ev)

        next_state = sympy.simplify_logic(sympy.And(global_state, con))
        if next_state == sympy.false:
            global_conflict = True
            table.add_row(str(con), "[bold red]CONFLICT[/]", ev_str)
        else:
            global_state = next_state
            table.add_row(str(con), "[green]OK[/]", ev_str)

    ui.raw.print(table)
    if not global_conflict:
        ui.out_info(f"Final configuration: {global_state}")
