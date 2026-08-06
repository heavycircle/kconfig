from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import sympy

from kconfig.core.analysis.structs import gather_struct_evidence
from kconfig.types import KconfigFieldType, KconfigStruct, KconfigStructField

if TYPE_CHECKING:
    import pytest

CONFIG_64BIT = sympy.Symbol("CONFIG_64BIT")
CONFIG_FOO = sympy.Symbol("CONFIG_FOO")


def _fake_get_typedef_configs(field_type: KconfigFieldType, module_type: str) -> sympy.Expr:
    """Stand in for real typedef resolution: only 'Elf_Sym' has known expansions."""
    base = field_type.original_type.split()[0]
    if base != "Elf_Sym":
        return sympy.true

    return {"Elf64_Sym": CONFIG_64BIT, "Elf32_Sym": sympy.Not(CONFIG_64BIT)}.get(module_type, sympy.false)


def _patch_module_lookup(monkeypatch: pytest.MonkeyPatch, module_struct: KconfigStruct) -> list[str]:
    """Patch get_module_struct to return a fixed layout, recording each lookup by name."""
    calls: list[str] = []

    def fake_get_module_struct(name: str) -> KconfigStruct:
        calls.append(name)
        return module_struct

    monkeypatch.setattr("kconfig.core.analysis.structs.structs.get_module_struct", fake_get_module_struct)
    monkeypatch.setattr("kconfig.core.analysis.structs.parser.get_typedef_configs", _fake_get_typedef_configs)
    return calls


def test_type_evidence_for_a_matching_typedef(monkeypatch: pytest.MonkeyPatch) -> None:
    root = KconfigStruct(
        "outer", Path("outer.h"), 1, fields=[KconfigStructField("sym", KconfigFieldType("Elf_Sym"), sympy.true)]
    )
    module = KconfigStruct(
        "outer", Path("outer.h"), 1, fields=[KconfigStructField("sym", KconfigFieldType("Elf64_Sym"), sympy.true)]
    )
    _patch_module_lookup(monkeypatch, module)

    evidence = gather_struct_evidence(root)
    assert len(evidence) == 1
    assert evidence[0].kind == "type"
    assert evidence[0].raw_guard == CONFIG_64BIT


def test_impossible_type_skips_the_field_and_its_recursion(monkeypatch: pytest.MonkeyPatch) -> None:
    inner_field = KconfigStructField("n", KconfigFieldType("int"), sympy.true)
    nested = KconfigStruct("inner", Path("inner.h"), 1, fields=[inner_field])
    root = KconfigStruct(
        "outer",
        Path("outer.h"),
        1,
        fields=[KconfigStructField("bad", KconfigFieldType("Elf_Sym", layout=nested), sympy.true)],
    )
    module = KconfigStruct(
        "outer", Path("outer.h"), 1, fields=[KconfigStructField("bad", KconfigFieldType("unrelated"), sympy.true)]
    )
    _patch_module_lookup(monkeypatch, module)

    assert gather_struct_evidence(root) == []


def test_presence_evidence_for_a_missing_guarded_field(monkeypatch: pytest.MonkeyPatch) -> None:
    root = KconfigStruct(
        "outer", Path("outer.h"), 1, fields=[KconfigStructField("guarded", KconfigFieldType("int"), CONFIG_FOO)]
    )
    module = KconfigStruct("outer", Path("outer.h"), 1, fields=[])
    _patch_module_lookup(monkeypatch, module)

    evidence = gather_struct_evidence(root)
    assert len(evidence) == 1
    assert evidence[0].is_enabled is False
    assert evidence[0].constraints == sympy.Not(CONFIG_FOO)


def test_uncontrollable_missing_field_produces_no_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    root = KconfigStruct(
        "outer", Path("outer.h"), 1, fields=[KconfigStructField("gone", KconfigFieldType("int"), sympy.true)]
    )
    module = KconfigStruct("outer", Path("outer.h"), 1, fields=[])
    _patch_module_lookup(monkeypatch, module)

    assert gather_struct_evidence(root) == []


def test_recursion_into_a_matching_nested_struct(monkeypatch: pytest.MonkeyPatch) -> None:
    nested = KconfigStruct(
        "inner", Path("inner.h"), 1, fields=[KconfigStructField("guarded", KconfigFieldType("int"), CONFIG_FOO)]
    )
    root = KconfigStruct(
        "outer",
        Path("outer.h"),
        1,
        fields=[KconfigStructField("has_nested", KconfigFieldType("struct inner", layout=nested), sympy.true)],
    )
    has_nested_field = KconfigStructField("has_nested", KconfigFieldType("struct inner"), sympy.true)
    outer_module = KconfigStruct("outer", Path("outer.h"), 1, fields=[has_nested_field])
    inner_module = KconfigStruct("inner", Path("inner.h"), 1, fields=[])

    def fake_get_module_struct(name: str) -> KconfigStruct:
        return {"outer": outer_module, "inner": inner_module}[name]

    monkeypatch.setattr("kconfig.core.analysis.structs.structs.get_module_struct", fake_get_module_struct)
    monkeypatch.setattr("kconfig.core.analysis.structs.parser.get_typedef_configs", _fake_get_typedef_configs)

    evidence = gather_struct_evidence(root)
    assert len(evidence) == 1
    assert evidence[0].struct_name == "inner"
    assert evidence[0].constraints == sympy.Not(CONFIG_FOO)


def test_evaluation_cache_short_circuits_repeated_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    root = KconfigStruct(
        "outer", Path("outer.h"), 1, fields=[KconfigStructField("plain", KconfigFieldType("int"), sympy.true)]
    )
    module = KconfigStruct(
        "outer", Path("outer.h"), 1, fields=[KconfigStructField("plain", KconfigFieldType("int"), sympy.true)]
    )
    calls = _patch_module_lookup(monkeypatch, module)

    first = gather_struct_evidence(root)
    second = gather_struct_evidence(root)
    assert calls == ["outer"]
    assert first is second


def test_cycle_protection_stops_self_referencing_structs(monkeypatch: pytest.MonkeyPatch) -> None:
    root = KconfigStruct("outer", Path("outer.h"), 1)
    root.fields = [KconfigStructField("self_ref", KconfigFieldType("struct outer", layout=root), sympy.true)]

    self_ref_field = KconfigStructField("self_ref", KconfigFieldType("struct outer"), sympy.true)
    module = KconfigStruct("outer", Path("outer.h"), 1, fields=[self_ref_field])
    _patch_module_lookup(monkeypatch, module)

    # Must terminate rather than recurse infinitely.
    assert gather_struct_evidence(root) == []
