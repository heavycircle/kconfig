from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import sympy

from kconfig.core.analysis.structs import gather_struct_guards
from kconfig.core.structs.kernel import get_signature_structs
from kconfig.exceptions import KconfigSymbolNotFoundError
from kconfig.types import KconfigFieldType, KconfigStruct, KconfigStructField

if TYPE_CHECKING:
    import pytest

CONFIG_FOO = sympy.Symbol("CONFIG_FOO")
CONFIG_BAR = sympy.Symbol("CONFIG_BAR")


def test_get_signature_structs_resolves_and_skips_unresolvable_members(monkeypatch: pytest.MonkeyPatch) -> None:
    net_device = KconfigStruct("net_device", Path("netdevice.h"), 1)

    def fake_get_kernel_struct(name: str, **_kwargs: object) -> KconfigStruct:
        if name == "net_device":
            return net_device
        raise KconfigSymbolNotFoundError(name, "linux-6.8")

    warnings: list[str] = []
    monkeypatch.setattr("kconfig.core.structs.kernel.get_kernel_struct", fake_get_kernel_struct)
    monkeypatch.setattr(
        "kconfig.core.structs.kernel.ui.out_warning", lambda *a, **_k: warnings.append(" ".join(map(str, a)))
    )

    resolved = get_signature_structs(["net_device", "missing_struct"], recursive=False)

    assert resolved == {"net_device": net_device}
    assert len(warnings) == 1


def test_gather_struct_guards_tags_fields_with_the_originating_member() -> None:
    inner = KconfigStruct(
        "inner", Path("inner.h"), 1, fields=[KconfigStructField("x", KconfigFieldType("int"), CONFIG_BAR)]
    )
    outer = KconfigStruct(
        "outer",
        Path("outer.h"),
        1,
        fields=[
            KconfigStructField("plain", KconfigFieldType("int"), sympy.true),
            KconfigStructField("guarded", KconfigFieldType("int"), CONFIG_FOO),
            KconfigStructField("nested", KconfigFieldType("struct inner", layout=inner), sympy.true),
        ],
    )

    guards = gather_struct_guards("outer", outer)

    assert len(guards) == 2
    assert all(g.member == "outer" for g in guards)

    by_field = {g.field_name: g for g in guards}
    assert by_field["guarded"].struct_name == "outer"
    assert by_field["guarded"].guard == CONFIG_FOO
    assert by_field["x"].struct_name == "inner"
    assert by_field["x"].guard == CONFIG_BAR


def test_gather_struct_guards_stops_at_a_self_referencing_cycle() -> None:
    cyclic = KconfigStruct("node", Path("node.h"), 1)
    cyclic.fields = [KconfigStructField("next", KconfigFieldType("struct node *", layout=cyclic), CONFIG_FOO)]

    guards = gather_struct_guards("node", cyclic)

    assert len(guards) == 1
    assert guards[0].field_name == "next"


def test_gather_struct_guards_does_not_recurse_when_layout_is_unresolved() -> None:
    # Mirrors a struct fetched with recursive=False: field_type.layout is
    # always None, so gather_struct_guards must not attempt to walk into it.
    outer = KconfigStruct(
        "outer", Path("outer.h"), 1, fields=[KconfigStructField("s", KconfigFieldType("struct inner"), CONFIG_FOO)]
    )

    guards = gather_struct_guards("outer", outer)

    assert len(guards) == 1
    assert guards[0].struct_name == "outer"
