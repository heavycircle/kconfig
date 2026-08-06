from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import sympy

from kconfig.core.analysis.structs import gather_struct_evidence
from kconfig.core.parser import ANONYMOUS_FIELD_PREFIX
from kconfig.exceptions import KconfigSymbolNotFoundError
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
    assert first == second


def test_shared_struct_evidence_is_included_once_not_per_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: a widely-shared type (list_head/spinlock_t in the real kernel)
    # referenced from many fields used to have its evidence re-extended once per
    # reference, which compounds combinatorially in a large, heavily-shared struct
    # graph like task_struct's. It must be included exactly once.
    shared = KconfigStruct(
        "shared", Path("shared.h"), 1, fields=[KconfigStructField("guarded", KconfigFieldType("int"), CONFIG_FOO)]
    )
    root = KconfigStruct(
        "outer",
        Path("outer.h"),
        1,
        fields=[
            KconfigStructField("a", KconfigFieldType("struct shared", layout=shared), sympy.true),
            KconfigStructField("b", KconfigFieldType("struct shared", layout=shared), sympy.true),
            KconfigStructField("c", KconfigFieldType("struct shared", layout=shared), sympy.true),
        ],
    )

    outer_module = KconfigStruct(
        "outer",
        Path("outer.h"),
        1,
        fields=[KconfigStructField(n, KconfigFieldType("struct shared"), sympy.true) for n in "abc"],
    )
    shared_module = KconfigStruct("shared", Path("shared.h"), 1, fields=[])  # "guarded" missing from the module

    def fake_get_module_struct(name: str) -> KconfigStruct:
        return {"outer": outer_module, "shared": shared_module}[name]

    monkeypatch.setattr("kconfig.core.analysis.structs.structs.get_module_struct", fake_get_module_struct)
    monkeypatch.setattr("kconfig.core.analysis.structs.parser.get_typedef_configs", _fake_get_typedef_configs)

    evidence = gather_struct_evidence(root)
    assert len(evidence) == 1
    assert evidence[0].struct_name == "shared"


def test_cycle_protection_stops_self_referencing_structs(monkeypatch: pytest.MonkeyPatch) -> None:
    root = KconfigStruct("outer", Path("outer.h"), 1)
    root.fields = [KconfigStructField("self_ref", KconfigFieldType("struct outer", layout=root), sympy.true)]

    self_ref_field = KconfigStructField("self_ref", KconfigFieldType("struct outer"), sympy.true)
    module = KconfigStruct("outer", Path("outer.h"), 1, fields=[self_ref_field])
    _patch_module_lookup(monkeypatch, module)

    # Must terminate rather than recurse infinitely.
    assert gather_struct_evidence(root) == []


def test_anonymous_nested_struct_is_skipped_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    # An anonymous nested struct has no name (KconfigStruct.original_name == ""), so
    # there's nothing to look up in the compiled module's layout for it independently.
    nested = KconfigStruct("", Path(), 3, fields=[KconfigStructField("x", KconfigFieldType("int"), sympy.true)])
    root = KconfigStruct(
        "outer",
        Path("outer.h"),
        1,
        fields=[KconfigStructField("point", KconfigFieldType("struct", layout=nested), sympy.true)],
    )
    outer_field = KconfigStructField("point", KconfigFieldType("struct"), sympy.true)
    outer_module = KconfigStruct("outer", Path("outer.h"), 1, fields=[outer_field])

    def fake_get_module_struct(name: str) -> KconfigStruct:
        if name == "outer":
            return outer_module
        raise KconfigSymbolNotFoundError(name, "fake_kernel")

    monkeypatch.setattr("kconfig.core.analysis.structs.structs.get_module_struct", fake_get_module_struct)
    monkeypatch.setattr("kconfig.core.analysis.structs.parser.get_typedef_configs", _fake_get_typedef_configs)

    # Must not crash -- just yields no evidence for the part it can't independently verify.
    assert gather_struct_evidence(root) == []


def test_anonymous_struct_never_triggers_a_module_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: an anonymous struct's own-evidence lookup used to call
    # get_module_struct("") anyway, which always fails and printed a
    # confusing "Cannot find definition for '' in ..." warning. There's
    # nothing to look up by name for an anonymous struct -- skip before ever
    # calling out to the module lookup at all.
    calls: list[str] = []

    def fake_get_module_struct(name: str) -> KconfigStruct:
        calls.append(name)
        raise KconfigSymbolNotFoundError(name, "fake_kernel")

    monkeypatch.setattr("kconfig.core.analysis.structs.structs.get_module_struct", fake_get_module_struct)

    anon = KconfigStruct("", Path(), 1, fields=[KconfigStructField("x", KconfigFieldType("int"), sympy.true)])
    gather_struct_evidence(anon)

    assert calls == []


def test_recursion_continues_through_an_anonymous_ancestor(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: when a struct's own evidence couldn't be determined
    # (anonymous, or missing from the module), gather_struct_evidence used to
    # return early and never recurse into its nested fields -- silently
    # dropping evidence from any *named* struct reachable behind an
    # anonymous or module-missing ancestor (a common C idiom: anonymous
    # unions/structs wrapping named nested types).
    named_nested = KconfigStruct(
        "named_nested",
        Path("named.h"),
        1,
        fields=[KconfigStructField("guarded", KconfigFieldType("int"), CONFIG_FOO)],
    )
    anon = KconfigStruct(
        "",
        Path(),
        1,
        fields=[KconfigStructField("n", KconfigFieldType("struct named_nested", layout=named_nested), sympy.true)],
    )
    root = KconfigStruct(
        "outer",
        Path("outer.h"),
        1,
        fields=[KconfigStructField("anon_field", KconfigFieldType("struct", layout=anon), sympy.true)],
    )

    named_nested_module = KconfigStruct("named_nested", Path("named.h"), 1, fields=[])  # "guarded" missing

    def fake_get_module_struct(name: str) -> KconfigStruct:
        if name == "named_nested":
            return named_nested_module
        raise KconfigSymbolNotFoundError(name, "fake_kernel")

    monkeypatch.setattr("kconfig.core.analysis.structs.structs.get_module_struct", fake_get_module_struct)
    monkeypatch.setattr("kconfig.core.analysis.structs.parser.get_typedef_configs", _fake_get_typedef_configs)

    evidence = gather_struct_evidence(root)
    assert len(evidence) == 1
    assert evidence[0].struct_name == "named_nested"
    assert evidence[0].constraints == sympy.Not(CONFIG_FOO)


def test_anonymous_member_field_does_not_warn_about_uncontrollable_absence(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: a true anonymous member (`struct { ... };`, no declarator at
    # all) gets a synthetic ANONYMOUS_FIELD_PREFIX-prefixed field name that can
    # never appear in a compiled module's layout by construction -- it used to
    # always fire a confusing, never-actionable "Uncontrollable field missing"
    # warning for every single one.
    warnings: list[str] = []
    monkeypatch.setattr(
        "kconfig.core.analysis.structs.ui.out_warning", lambda *a, **_k: warnings.append(" ".join(map(str, a)))
    )

    synthetic_name = f"{ANONYMOUS_FIELD_PREFIX}12345"
    root = KconfigStruct(
        "outer",
        Path("outer.h"),
        1,
        fields=[KconfigStructField(synthetic_name, KconfigFieldType("struct"), sympy.true)],
    )
    module = KconfigStruct("outer", Path("outer.h"), 1, fields=[])  # synthetic field can never match
    _patch_module_lookup(monkeypatch, module)

    assert gather_struct_evidence(root) == []
    assert warnings == []
