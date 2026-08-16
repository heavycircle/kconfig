from __future__ import annotations

from typing import TYPE_CHECKING

import sympy
from rich.table import Table

from kconfig.core import parser, structs
from kconfig.exceptions import KconfigSymbolNotFoundError
from kconfig.types import KconfigEvidence, KconfigMemberGuard
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
    elif not has_match and not field.field_name.startswith(parser.ANONYMOUS_FIELD_PREFIX):
        # A true anonymous member (`struct { ... };`, no variable name at all)
        # gets a synthetic field_name that can never appear in a compiled
        # module's layout by construction -- not a real absence, just nothing
        # to check presence against.
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
    if not name:
        # Anonymous struct: no name to look up a module-side layout by at
        # all (pahole has nothing to key it by either) -- not an error, just
        # nothing we can check field presence/type against.
        return None

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

    If this struct's own evidence can't be determined (anonymous, or missing
    from the module entirely), it contributes no evidence of its own but
    recursion into its nested fields still proceeds -- a named struct several
    levels deep behind an anonymous or module-missing ancestor is common and
    still independently checkable.

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
    evidence_list = list(own_evidence) if own_evidence is not None else []
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


def gather_struct_guards(
    member: str, struct: KconfigStruct, visited: set[str | int] | None = None
) -> list[KconfigMemberGuard]:
    """Collect every non-trivial CONFIG guard written on a struct's fields.

    Unlike gather_struct_evidence, this only reflects what's structurally
    written in the kernel source (#ifdef nesting) -- no module comparison is
    involved, so it works without a module directory at all.

    Args:
        member (str): The signature's top-level custom member this struct was
            reached from. Recorded on every guard found, however deep the
            recursion goes, so results from several members can be told
            apart once combined.
        struct (KconfigStruct): The struct to walk. Only fields with a
            resolved nested layout are recursed into -- i.e. this respects
            whatever ``recursive`` value the struct was originally built
            with.
        visited (set[str | int] | None): Keys on the current ancestor path,
            to detect a struct nested inside itself.

    Returns:
        list[KconfigMemberGuard]: One entry per guarded field found.

    """
    if visited is None:
        visited = set()

    key = _struct_key(struct)
    if key in visited:
        return []
    branch_visited = visited | {key}

    guards: list[KconfigMemberGuard] = []
    for field in struct.fields:
        if field.guard is not sympy.true:
            struct_name = struct.original_name or "(anonymous)"
            guards.append(KconfigMemberGuard(member, struct_name, field.field_name, field.guard))
        if field.field_type.layout is not None:
            guards.extend(gather_struct_guards(member, field.field_type.layout, branch_visited))

    return guards


def _config_dict(model: dict[sympy.Basic, bool]) -> dict[str, bool]:
    """Reduce a sympy satisfiability model to its ``CONFIG_*`` entries, string-keyed for JSON."""
    return {str(sym): val for sym, val in model.items() if str(sym).startswith("CONFIG_")}


ConstraintRow = tuple[sympy.Expr, "list[KconfigEvidence]", bool, sympy.Basic]
"""One resolved constraint: (constraint, its evidence, whether it conflicted, cumulative state after it)."""


def _resolve_constraints(constraints: dict[sympy.Expr, list[KconfigEvidence]]) -> tuple[list[ConstraintRow], bool]:
    """Fold every constraint into a cumulative state, in application order.

    Returns:
        tuple[list[ConstraintRow], bool]: Per-constraint rows (for rendering),
            and whether any constraint conflicted with the accumulated state.

    """
    global_state = sympy.true
    global_conflict = False
    rows: list[ConstraintRow] = []

    for con, ev_list in constraints.items():
        next_state = sympy.simplify_logic(sympy.And(global_state, con))
        conflict = next_state == sympy.false or not sympy.satisfiable(next_state)
        if conflict:
            global_conflict = True
        else:
            global_state = next_state
        rows.append((con, ev_list, conflict, global_state))

    return rows, global_conflict


def _render_constraint_table(root_name: str, rows: list[ConstraintRow]) -> Table:
    table = Table(title=f"Analysis: {root_name}")
    table.add_column("Applied Constraint", style="yellow")
    table.add_column("Status", justify="center")
    table.add_column("Evidence & Raw Guard", style="cyan")
    table.add_column("Cumulative State", style="green")

    for con, ev_list, conflict, state in rows:
        ev_str = "\n".join({f"- {e} [dim italic](Raw Guard: {e.raw_guard})[/]" for e in ev_list})
        if conflict:
            table.add_row(str(con), "[bold red]CONFLICT[/]", ev_str, "[dim red]UNSOLVABLE[/]")
        else:
            table.add_row(str(con), "[bold green]OK[/]", ev_str, str(state))

    return table


def _gather_forest_evidence(roots: dict[str, KconfigStruct]) -> list[KconfigEvidence]:
    """Gather evidence from every root struct, counting a struct shared between roots only once."""
    included: set[str | int] = set()
    evidence: list[KconfigEvidence] = []
    for struct in roots.values():
        key = _struct_key(struct)
        if key in included:
            continue
        included.add(key)
        evidence.extend(gather_struct_evidence(struct, included=included))
    return evidence


def analyze_structs(roots: dict[str, KconfigStruct], current: str | None = None, output_format: str = "table") -> None:
    """Analyze one or more struct trees together and report the enabled configs.

    This method aims to complete. On error, it will print the error and keep
    running. These errors either mean an error in the parsing of the kernel
    or modules.

    Args:
        roots (dict[str, KconfigStruct]): Struct trees to recursively parse,
            keyed by a label for display (e.g. a struct's own name, or --
            when several structs are analyzed together, such as a function
            signature's custom members -- the member each root was reached
            from). Evidence from a struct reached through more than one root
            (directly, or nested under another root) is only counted once.
        current (str | None): Path to a .config file for rendering a diff.
        output_format (str): Either ``"table"`` (a human-readable Rich table,
            the default) or ``"json"`` (a single JSON document on stdout, for
            scripting -- no Rich table or status messages are printed).

    """
    as_json = output_format == "json"
    title = ", ".join(roots)

    evidence = _gather_forest_evidence(roots)
    if not evidence:
        if as_json:
            ui.raw.print_json(data={"conflict": False, "config": {}})
        else:
            ui.out_info(f"No CONFIG guards found in '{title}'")
        return

    constraints: dict[sympy.Expr, list[KconfigEvidence]] = {}
    for e in evidence:
        constraints.setdefault(e.constraints, []).append(e)

    rows, global_conflict = _resolve_constraints(constraints)
    global_state = rows[-1][3]

    if not as_json:
        ui.out_info("Rendering table ...")
        ui.raw.print(_render_constraint_table(title, rows))

    if global_conflict:
        if as_json:
            ui.raw.print_json(data={"conflict": True})
        else:
            ui.out_error("Impossible layout! Conflicting requirements detected.")
        return

    models = list(sympy.satisfiable(global_state, all_models=True))

    if as_json:
        result = {"conflict": False, "config": _config_dict(models[0]), "valid_configurations": len(models)}
        ui.raw.print_json(data=result)
        return

    ui.out_success(f"Final Required Configuration: {global_state}")
    ui.out_success(f"Found {len(models)} valid configurations to satisfy these constraints.")

    if current and models[0]:
        current_config = parser.parse_config_file(current)

        ui.out_info("Rendering diff ...")
        render_config_diff_table(current_config, models[0])


def analyze_struct_tree(root_struct: KconfigStruct, current: str | None = None, output_format: str = "table") -> None:
    """Analyze a single struct tree and report the enabled configs.

    A thin wrapper around ``analyze_structs`` for the common single-struct
    case (e.g. ``kconfig struct analyze``). See its docstring for details.

    Args:
        root_struct (KconfigStruct): The struct to recursively parse.
        current (str | None): Path to a .config file for rendering a diff.
        output_format (str): Either ``"table"`` or ``"json"``.

    """
    analyze_structs({root_struct.original_name: root_struct}, current=current, output_format=output_format)
