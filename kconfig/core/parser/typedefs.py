from __future__ import annotations

import sympy

from kconfig.core.cache import get_typedef_locations
from kconfig.core.query import parse_source
from kconfig.core.utils import strip_type_modifiers
from kconfig.types import KconfigFieldType, KconfigParserState, KconfigResolvedType

from .dispatcher import dispatch

TYPEDEF_RESOLVE_CACHE: dict[str, list[KconfigResolvedType]] = {}


def resolve_typedef(name: str) -> list[KconfigResolvedType]:
    """Resolve every known expansion of a typedef or macro alias.

    Parses each file that defines ``name`` (per the typedef location cache)
    with a fresh parser state, so nested ``#ifdef``s are threaded into a
    CONFIG guard the same way struct fields are.

    Args:
        name (str): The typedef or macro name to resolve (e.g. ``Elf_Sym``).

    Returns:
        list[KconfigResolvedType]: Every guarded expansion found for ``name``.

    """
    if name in TYPEDEF_RESOLVE_CACHE:
        return TYPEDEF_RESOLVE_CACHE[name]

    resolved: list[KconfigResolvedType] = []
    for file in get_typedef_locations(name):
        state = KconfigParserState()
        dispatch.dispatch(parse_source(file.read_bytes()), state)

        resolved.extend(
            KconfigResolvedType(f.field_type.original_type, file, f.guard) for f in state.fields if f.field_name == name
        )

    TYPEDEF_RESOLVE_CACHE[name] = resolved
    return resolved


def get_typedef_configs(field_type: KconfigFieldType, module_type: str) -> sympy.Expr:
    """Infer the CONFIG guard implied by a module's observed type for a field.

    For example, a field declared as ``Elf_Sym`` that pahole reports as
    ``Elf64_Sym`` implies ``CONFIG_64BIT``, since the kernel headers only
    ``#define Elf_Sym Elf64_Sym`` under that guard. Also populates
    ``field_type.resolved_types`` with every candidate expansion found, for
    downstream rendering (e.g. ``kconfig type find``).

    Args:
        field_type (KconfigFieldType): The field's type as declared in the kernel source.
        module_type (str): The field's type as observed in the compiled module.

    Returns:
        sympy.Expr: ``sympy.true`` if there's no evidence either way,
            ``sympy.false`` if ``module_type`` is unreachable from any known
            expansion, otherwise the guard(s) under which it's reachable.

    """
    if field_type.original_type == module_type:
        return sympy.true

    base_name, _ = strip_type_modifiers(field_type.original_type)
    candidates = resolve_typedef(base_name)
    if not candidates:
        return sympy.true

    field_type.resolved_types = candidates
    module_base, _ = strip_type_modifiers(module_type)
    matching = [c.guard for c in candidates if strip_type_modifiers(c.resolved_type)[0] == module_base]
    return sympy.Or(*matching)
