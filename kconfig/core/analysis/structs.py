from __future__ import annotations

from typing import TYPE_CHECKING

import sympy
from rich.table import Table

from kconfig.core import parser, structs
from kconfig.exceptions import KconfigSymbolNotFoundError
from kconfig.types import KconfigEvidence
from kconfig.ui import render_config_diff_table, ui

from .guards import parse_config_guard

if TYPE_CHECKING:
    from kconfig.types import KconfigStruct, KconfigStructField, KconfigStructFields

EVALUATION_CACHE: dict[str | int, list[KconfigEvidence]] = {}
"""Cache of a struct's own field evidence (no recursion), keyed by name -- or,
for anonymous structs (which have no name), by object identity."""


def _get_module_layout(name: str) -> KconfigStructFields | None:
    """Fetch the compiled module's field layout for a struct, if it's known."""
    try:
        module_struct = structs.get_module_struct(name)
    except KconfigSymbolNotFoundError as e:
        ui.out_warning(f"{e}, skipping ...")
        return None

    return {f.field_name: f.field_type.original_type for f in module_struct.fields}


def _type_evidence(
    struct_name: str, field: KconfigStructField, type_guard: sympy.Expr, module_type: str
) -> KconfigEvidence:
    """Build evidence from a field's type matching a guarded typedef expansion."""
    return KconfigEvidence(
        struct_name,
        f"{field.field_type.original_type} {field.field_name}",
        True,
        type_guard,
        type_guard,
        kind="type",
        type=module_type,
    )


def _presence_evidence(struct_name: str, field: KconfigStructField, has_match: bool) -> KconfigEvidence:
    """Build evidence from a guarded field's presence (or absence) in the module."""
    raw_expr = parse_config_guard(str(field.guard))
    applied = raw_expr if has_match else sympy.Not(raw_expr)
    field_desc = f"{field.field_type.original_type} {field.field_name}"
    return KconfigEvidence(struct_name, field_desc, has_match, raw_expr, applied)


def _evaluate_field(
    struct_name: str, field: KconfigStructField, layout: KconfigStructFields
) -> list[KconfigEvidence] | None:
    """Gather the evidence a single struct field contributes.

    Returns:
        list[KconfigEvidence] | None: The evidence found (possibly empty), or
            ``None`` if the field's type could never match the module's
            observed layout -- the caller should skip the field entirely.

    """
    has_match = field.field_name in layout
    evidence: list[KconfigEvidence] = []

    if has_match:
        module_type = layout[field.field_name]
        type_guard = parser.get_typedef_configs(field.field_type, module_type)

        if type_guard == sympy.false:
            ui.out_warning(f"Impossible: Cannot match types ({field.field_name}): {module_type}")
            return None

        if type_guard is not sympy.true:
            evidence.append(_type_evidence(struct_name, field, type_guard, module_type))

    if field.guard is not sympy.true:
        evidence.append(_presence_evidence(struct_name, field, has_match))
    elif not has_match:
        ui.out_warning(f"Uncontrollable field missing in '{struct_name}': '{field.field_name}'")

    return evidence


def _struct_key(struct: KconfigStruct) -> str | int:
    """A cache/visited key for a struct.

    Its name, or -- for an anonymous struct, which has none -- its object
    identity. Two anonymous structs are never the same type just because
    they share the (empty) name.
    """
    return struct.original_name or id(struct)


def _get_own_evidence(struct: KconfigStruct, key: str | int) -> list[KconfigEvidence] | None:
    """Evidence from this struct's own fields, without recursing into nested layouts.

    Memoized by ``key`` since it depends only on the struct and the module's
    layout, not on how or how many times it was reached.

    Returns:
        list[KconfigEvidence] | None: The evidence found (possibly empty), or
            ``None`` if the module doesn't have this struct at all.

    """
    if key in EVALUATION_CACHE:
        return EVALUATION_CACHE[key]

    name = struct.original_name
    layout = _get_module_layout(name)
    if layout is None:
        return None

    struct_name = name or "anonymous"
    evidence_list: list[KconfigEvidence] = []
    for field in struct.fields:
        field_evidence = _evaluate_field(struct_name, field, layout)
        if field_evidence is not None:
            evidence_list.extend(field_evidence)

    EVALUATION_CACHE[key] = evidence_list
    return evidence_list


def gather_struct_evidence(
    struct: KconfigStruct, visited: set[str | int] | None = None, included: set[str | int] | None = None
) -> list[KconfigEvidence]:
    """Get all evidence for a struct.

    This method parses the struct's fields, checking the config guards inside
    the struct, comparing them to the provided modules. It must check both the
    field presence and the type match to confirm the config is enabled or not.

    This method always does a recursive parse of the structure. If --recursive
    was not passed, the struct just won't have recursive elements.

    This method requires state.module_dir be set.

    Args:
        struct (KconfigStruct): The struct to parse.
        visited (set[str | int] | None): Keys on the current ancestor path, to
            detect a struct nested inside itself.
        included (set[str | int] | None): Every struct already incorporated
            into this analysis, anywhere -- not just the current ancestor
            path -- so a type referenced from hundreds of places (very common
            for things like ``list_head``/``spinlock_t``) contributes its
            evidence once instead of once per reference.

    Returns:
        list[KconfigEvidence]: CONFIG evidence found inside this struct.

    """
    if visited is None:
        visited = set()
    if included is None:
        included = set()

    key = _struct_key(struct)
    if key in visited:
        return []

    own_evidence = _get_own_evidence(struct, key)
    if own_evidence is None:
        return []

    evidence_list = list(own_evidence)
    branch_visited = visited | {key}
    for field in struct.fields:
        nested = field.field_type.layout
        if nested is None:
            continue

        nested_key = _struct_key(nested)
        if nested_key in included:
            continue
        included.add(nested_key)

        evidence_list.extend(gather_struct_evidence(nested, visited=branch_visited, included=included))

    return evidence_list


def analyze_struct_tree(root_struct: KconfigStruct, current: str | None = None) -> None:
    """Analyze a tree of structs and render a table of enabled configs.

    This method aims to complete. On error, it will print the error and keep
    running. These errors either mean an error in the parsing of the kernel
    or modules.

    Args:
        root_struct (KconfigStruct): The struct to recursively parse.
        current (str | None): Path to a .config file for rendering a diff.

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
        return

    ui.out_success(f"Final Required Configuration: {global_state}")
    models = list(sympy.satisfiable(global_state, all_models=True))
    ui.out_success(f"Found {len(models)} valid configurations to satisfy these constraints.")

    if current and models[0]:
        current_config = parser.parse_config_file(current)

        ui.out_info("Rendering diff ...")
        render_config_diff_table(current_config, models[0])
