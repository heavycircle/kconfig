from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.cli import kernel

if TYPE_CHECKING:
    import pytest


def test_fetch_debian_accepts_release_number(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_fetch_distro_source(
        _archive_urls: list[str],
        pockets: list[str],
        _package: str,
        _version: str | None,
    ) -> None:
        captured["pockets"] = pockets

    monkeypatch.setattr(kernel, "_fetch_distro_source", fake_fetch_distro_source)

    kernel.kernel_fetch_debian(version=None, release="12", package="linux")

    assert captured["pockets"] == [
        "bookworm",
        "bookworm-updates",
        "bookworm-security",
    ]


def test_list_debian_accepts_release_number(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_list_distro_packages(
        _archive_urls: list[str],
        pockets: list[str],
        _package: str,
    ) -> list[object]:
        captured["pockets"] = pockets
        return []

    def noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(kernel, "_list_distro_packages", fake_list_distro_packages)
    monkeypatch.setattr(kernel, "render_distro_package_table", noop)

    kernel.kernel_list_debian(release="12", package="linux")

    assert captured["pockets"] == [
        "bookworm",
        "bookworm-updates",
        "bookworm-security",
    ]
