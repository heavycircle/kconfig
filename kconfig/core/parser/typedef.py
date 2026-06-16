from __future__ import annotations

from kconfig.core import cache, config, utils
from kconfig.types import KconfigFieldGuard, KconfigFieldType, KconfigResolvedType
from kconfig.ui import ui

from .query import run_query
from .utils import get_enclosing_configs

TYPEDEF_CACHE: dict[str, KconfigFieldType] = {}
"""Cache holding typedef resolutions."""

PRIMITIVE_TYPES = ["char", "int", "long", "short", "void"]
"""Primitive types that we shouldn't try to typedef."""


def get_typedef_configs(symbol: KconfigFieldType, to_match: str) -> KconfigFieldGuard:
    """Get the configs that yield a certain resolved type.

    Since any of the configs can yield that type, they are OR'ed together.

    """
    normal_match = utils.normalize_type(to_match)
    if normal_match == utils.normalize_type(symbol.original_type):
        return KconfigFieldGuard()  # Guaranteed state

    guard = KconfigFieldGuard(operand="||")
    for resolve in symbol.resolved_type:
        if normal_match == utils.normalize_type(resolve.true_type) and resolve.depends:
            guard.expression.append(resolve.depends)

    if len(guard.expression) == 0:
        return KconfigFieldGuard(is_enabled=False)  # Impossible state
    return guard


def get_symbol_typedef(type_name: str) -> KconfigFieldType:
    """Find a typedef for a symbol name inside the kernel."""
    base_type, suffix = utils.strip_type_modifiers(type_name)
    normal_type = utils.normalize_type(base_type)

    typedef = KconfigFieldType(type_name)
    if normal_type in PRIMITIVE_TYPES:
        return typedef

    definitions = cache.get_typedef_locations(normal_type)
    for file in definitions:
        contents = file.read_bytes()
        for _, captures in run_query("typedef-list", contents):
            typedef_key = utils.get_capture_text(captures, "typedef.name")
            typedef_val = utils.get_capture_text(captures, "typedef.type")
            if not (typedef_key and typedef_val):
                continue

            found_key = typedef_key[0].decode("utf-8", errors="replace").strip()
            found_val = typedef_val[0].decode("utf-8", errors="replace").strip()
            if normal_type == found_key:
                typedef_node = captures["typedef.name"][0]
                rel_file = file.relative_to(config.state.kernel_dir)

                # TODO (heavycircle): This goes as high as the .h ifndef/define guards.
                configs = get_enclosing_configs(typedef_node.parent)
                typedef.resolved_type.append(KconfigResolvedType(f"{found_val}{suffix}", rel_file, depends=configs))

    ui.out_debug(f"get_symbol_typedef ({type_name}): Found {len(typedef.resolved_type)} resolutions!")
    return typedef
