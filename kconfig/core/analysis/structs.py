from __future__ import annotations

from typing import TYPE_CHECKING

import sympy
from rich.table import Table

from kconfig.core import config, parser, structs
from kconfig.exceptions import KconfigSymbolNotFoundError
from kconfig.types import KconfigEvidence
from kconfig.ui import ui

from .guards import parse_config_guard


if TYPE_CHECKING:
    from kconfig.types import KconfigStruct

EVALUATION_CACHE: dict[str, list[KconfigEvidence]] = {}
"""Cache of structure names and their configuation evidence."""


def gather_struct_evidence(struct: KconfigStruct, visited: set[str] | None = None) -> list[KconfigEvidence]:
    """Get all evidence for a struct.

    This method parses the struct's fields, checking the config guards inside
    the struct, comparing them to the provided modules. It must check both the
    field presence and the type match to confirm the config is enabled or not.

    This method always does a recursive parse of the structure. If --recursive
    was not passed, the struct just won't have recursive elements.

    This method requires state.module_dir be set.

    Args:
        struct (KconfigStruct): The struct to parse.
        visited (set[str] | None): The set of visited structs.

    Returns:
        list[KconfigEvidence]: CONFIG evidence found inside this struct.

    """
    if visited is None:
        visited = set()

    # Check the cache, stop cycles.
    name = struct.original_name
    if name and name in visited:
        ui.out_debug(f"Cycle detected: {name}")
        return []
    if name and name in EVALUATION_CACHE:
        ui.out_debug(f"Cache hit: {name}")
        return EVALUATION_CACHE[name]
    if name:
        visited.add(name)

    try:
        layout = structs.get_module_struct(config.state.module_dir, name) if name else {}
    except KconfigSymbolNotFoundError as e:
        ui.out_warning(f"{e}, skipping ...")
        return []

    evidence_list: list[KconfigEvidence] = []
    for field in struct.fields:
        has_match = field.field_name in layout

        if has_match:
            module_type = layout[field.field_name]

            # Check this field's type
            type_guard = parser.get_typedef_configs(field.field_type, module_type)
            if type_guard.is_impossible:
                ui.out_warning(f"Impossible: Cannot match types ({field.field_name}): {module_type}")
                continue

            if type_guard.is_conditional:
                type_expr = parse_config_guard(str(type_guard))
                evidence_list.append(
                    KconfigEvidence(
                        name or "anonymous",
                        f"{field.field_type.original_type} {field.field_name}",
                        True,
                        type_expr,
                        type_expr,
                        kind="type",
                        type=layout[field.field_name],
                    )
                )

        if field.depends:
            # Check for member presence.
            raw_expr = parse_config_guard(str(field.depends))
            has_match = field.field_name in layout
            applied = raw_expr if has_match else sympy.Not(raw_expr)

            evidence_list.append(
                KconfigEvidence(
                    name or "anonymous",
                    f"{field.field_type.original_type} {field.field_name}",
                    has_match,
                    raw_expr,
                    applied,
                )
            )

        # Make recursive calls.
        if field.field_type.layout is not None:
            evidence_list.extend(gather_struct_evidence(field.field_type.layout, visited=visited))

    if name:
        visited.remove(name)
        EVALUATION_CACHE[name] = evidence_list

    return evidence_list


def analyze_struct_tree(root_struct: KconfigStruct) -> None:
    """Analyze a tree of structs and render a table of enabled configs.

    Args:
        root_struct (KconfigStruct): The struct to recursively parse.
    """
    evidence = gather_struct_evidence(root_struct)
    if not evidence:
        ui.out_info(f"No CONFIG guards found in '{root_struct.original_name}'")
        return

    constraints: dict[sympy.Expr, list[KconfigEvidence]] = {}
    for e in evidence:
        constraints.setdefault(e.constraints, []).append(e)

    global_state = sympy.true
    global_conflict = False

    # FIX: Redefined columns to perfectly match the data being injected
    table = Table(title=f"Analysis: {root_struct.original_name}")
    table.add_column("Applied Constraint", style="yellow")
    table.add_column("Status", justify="center")
    table.add_column("Evidence & Raw Guard", style="cyan")
    table.add_column("Cumulative State", style="green")

    for con, ev_list in constraints.items():
        ev_str = "\n".join({f"- {e} [dim italic](Raw Guard: {e.raw_guard})[/]" for e in ev_list})

        # Check for conflicts
        next_state = sympy.simplify_logic(sympy.And(global_state, con))
        if next_state == sympy.false or not sympy.satisfiable(next_state):
            global_conflict = True
            table.add_row(str(con), "[bold red]CONFLICT[/]", ev_str, "[dim red]UNSOLVABLE[/]")
        else:
            global_state = next_state
            table.add_row(str(con), "[bold green]OK[/]", ev_str, str(global_state))

    ui.out_info("Rendering table ...")
    ui.raw.print(table)

    if global_conflict:
        ui.out_error("Impossible layout! Conflicting requirements detected.")
    else:
        # Since we used simplify_logic inside the loop, global_state is already simplified!
        ui.out_success(f"Final Required Configuration: {global_state}")

        # Calculate exact valid combinations
        models = list(sympy.satisfiable(global_state, all_models=True))
        if models and models[0] is not False:
            ui.out_success(f"Found {len(models)} valid configurations to satisfy these constriants.")
