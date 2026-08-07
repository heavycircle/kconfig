from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import requests

from kconfig.cli import kernel

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pytest


def test_initial_release_has_fallback_url() -> None:
    urls = kernel.kernel_tarball_urls("6.8.0")
    assert urls == [
        "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.8.0.tar.xz",
        "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.8.tar.xz",
    ]


def test_patch_release_has_single_url() -> None:
    urls = kernel.kernel_tarball_urls("6.8.11")
    assert urls == [
        "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.8.11.tar.xz",
    ]


class FakeResponse:
    def __init__(self, status_code: int, body: bytes = b"") -> None:
        self.status_code = status_code
        self.body = body

    def __enter__(self) -> FakeResponse:  # noqa: PYI034
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    @property
    def headers(self) -> dict[str, str]:
        return {"content-length": str(len(self.body))}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)

    def iter_content(self, chunk_size: int = 8192) -> Iterator[bytes]:  # noqa: ARG002
        yield self.body


class FakeProgress:
    def __enter__(self) -> FakeProgress:  # noqa: PYI034
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def add_task(self, *_args: object, **_kwargs: object) -> int:
        return 0

    def update(self, *_args: object, **_kwargs: object) -> None:
        return None


class FakeTar:
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> FakeTar:  # noqa: PYI034
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def extractall(self, path: Path) -> None:
        (path / Path(self.name).name.removesuffix(".tar.xz")).mkdir()


def _noop(*_args: object, **_kwargs: object) -> None:
    return None


def _fake_open(path: str, _mode: object) -> FakeTar:
    return FakeTar(path)


def test_fetch_falls_back_to_initial_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    calls: list[str] = []

    def fake_get(url: str, **_kwargs: object) -> FakeResponse:
        calls.append(url)
        if url.endswith("linux-6.8.0.tar.xz"):
            return FakeResponse(404)
        return FakeResponse(200, b"archive")

    monkeypatch.setattr(kernel, "CACHE_KERNEL_DIR", cache)
    monkeypatch.setattr(kernel.ui, "out_info", _noop)
    monkeypatch.setattr(kernel.ui, "out_success", _noop)
    monkeypatch.setattr(kernel.ui, "out_error", _noop)
    monkeypatch.setattr(kernel.requests, "get", fake_get)
    monkeypatch.setattr(kernel, "_make_download_progress", FakeProgress)
    monkeypatch.setattr(kernel.tarfile, "open", _fake_open)

    kernel.kernel_fetch("6.8.0")

    assert calls == kernel.kernel_tarball_urls("6.8.0")
    assert (cache / "linux-6.8.0").is_dir()
    assert not (cache / "linux-6.8").exists()
