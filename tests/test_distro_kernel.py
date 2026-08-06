from __future__ import annotations

import gzip
import hashlib
from typing import TYPE_CHECKING, Self

import pytest

from kconfig.core.cache.distro_kernel import (
    DistroSourceFile,
    DistroSourcePackage,
    download_source_package,
    extract_source_package,
    find_latest_source_package,
    find_source_package,
    list_source_packages,
)
from kconfig.exceptions import KconfigFileInvalidError, KconfigSubprocessFailedError, KconfigSymbolNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

_FAKE_SOURCES = b"""Package: other-package
Format: 1.0
Version: 1.0-1
Directory: pool/main/o/other-package
Checksums-Sha256:
 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 100 other-package_1.0-1.dsc

Package: linux
Format: 1.0
Version: 6.8.0-31.31
Directory: pool/main/l/linux
Binary: linux-image-6.8.0-31-generic, linux-headers-6.8.0-31-generic
Checksums-Sha256:
 6689c76a5d61f282ef01adf3ef9d9afa0fc8316e1575a10a0a212d6987e9633e 8444 linux_6.8.0-31.31.dsc
 26512115972bdf017a4ac826cc7d3e9b0ba397d4f85cd330e4e4ff54c78061c 230060117 linux_6.8.0.orig.tar.gz
 21ba797c2f212456ded0de09e5d016a857a070d43513522df5d1b414ca94de0 1162846 linux_6.8.0-31.31.diff.gz

"""


class _FakeGetResponse:
    """Stands in for a plain (non-streaming) ``requests.get(...)`` call."""

    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = status_code
        self.content = content


def test_find_source_package_matches_exact_package_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "kconfig.core.cache.distro_kernel.requests.get",
        lambda *_a, **_k: _FakeGetResponse(200, gzip.compress(_FAKE_SOURCES)),
    )

    pkg = find_source_package("http://archive.example", ["noble"], "linux", "6.8.0-31.31")
    assert pkg.directory == "pool/main/l/linux"
    assert pkg.dsc_file.name == "linux_6.8.0-31.31.dsc"
    assert {f.name for f in pkg.files} == {
        "linux_6.8.0-31.31.dsc",
        "linux_6.8.0.orig.tar.gz",
        "linux_6.8.0-31.31.diff.gz",
    }


def test_find_source_package_raises_when_version_not_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "kconfig.core.cache.distro_kernel.requests.get",
        lambda *_a, **_k: _FakeGetResponse(200, gzip.compress(_FAKE_SOURCES)),
    )

    with pytest.raises(KconfigSymbolNotFoundError):
        find_source_package("http://archive.example", ["noble"], "linux", "9.9.9-1.1")


def test_find_source_package_tries_every_pocket(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_urls: list[str] = []

    def fake_get(url: str, **_kwargs: object) -> _FakeGetResponse:
        seen_urls.append(url)
        # Only the second pocket ("noble-updates") actually has anything.
        if "noble-updates" in url:
            return _FakeGetResponse(200, gzip.compress(_FAKE_SOURCES))
        return _FakeGetResponse(404, b"")

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    pkg = find_source_package("http://archive.example", ["noble", "noble-updates"], "linux", "6.8.0-31.31")
    assert pkg.directory == "pool/main/l/linux"
    assert len(seen_urls) == 2


_FAKE_SOURCES_OLDER_LINUX = b"""Package: linux
Format: 1.0
Version: 6.8.0-30.30
Directory: pool/main/l/linux
Checksums-Sha256:
 1111111111111111111111111111111111111111111111111111111111111111 8444 linux_6.8.0-30.30.dsc

"""


def test_find_latest_source_package_picks_the_newest_across_pockets(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **_kwargs: object) -> _FakeGetResponse:
        # "noble" (checked first) has the OLDER version; the newer one is in
        # "noble-updates" -- the newest must still win regardless of pocket order.
        if "noble-updates" in url:
            return _FakeGetResponse(200, gzip.compress(_FAKE_SOURCES))
        return _FakeGetResponse(200, gzip.compress(_FAKE_SOURCES_OLDER_LINUX))

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    pkg = find_latest_source_package("http://archive.example", ["noble", "noble-updates"], "linux")
    assert pkg.version == "6.8.0-31.31"


def test_list_source_packages_dedupes_and_sorts_newest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **_kwargs: object) -> _FakeGetResponse:
        # The newer version lives in both "noble" and "noble-updates" -- it
        # must appear only once in the result, not twice.
        if "noble-updates" in url:
            return _FakeGetResponse(200, gzip.compress(_FAKE_SOURCES))
        return _FakeGetResponse(200, gzip.compress(_FAKE_SOURCES + _FAKE_SOURCES_OLDER_LINUX))

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    packages = list_source_packages("http://archive.example", ["noble", "noble-updates"], "linux")

    assert [p.version for p in packages] == ["6.8.0-31.31", "6.8.0-30.30"]
    assert packages[0].binary == "linux-image-6.8.0-31-generic, linux-headers-6.8.0-31-generic"


class _FakeStreamResponse:
    """Stands in for ``requests.get(..., stream=True)``'s context-manager interface."""

    def __init__(self, body: bytes) -> None:
        self._body = body
        self.headers = {"content-length": str(len(body))}

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int) -> list[bytes]:
        return [self._body[i : i + chunk_size] for i in range(0, len(self._body), chunk_size)]


def test_download_source_package_verifies_checksums(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = b"pretend .dsc contents"
    good_sha = hashlib.sha256(body).hexdigest()

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", lambda *_a, **_k: _FakeStreamResponse(body))

    pkg = DistroSourcePackage(
        directory="pool/main/l/linux", version="1.0-1", files=[DistroSourceFile("linux_1.dsc", good_sha)]
    )
    dsc_path = download_source_package("http://archive.example", pkg, tmp_path)
    assert dsc_path == tmp_path / "linux_1.dsc"
    assert dsc_path.read_bytes() == body


def test_download_source_package_rejects_bad_checksum(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = b"pretend .dsc contents"
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", lambda *_a, **_k: _FakeStreamResponse(body))

    pkg = DistroSourcePackage(
        directory="pool/main/l/linux", version="1.0-1", files=[DistroSourceFile("linux_1.dsc", "0" * 64)]
    )
    with pytest.raises(KconfigFileInvalidError):
        download_source_package("http://archive.example", pkg, tmp_path)


def test_download_source_package_reports_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = b"x" * 100
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", lambda *_a, **_k: _FakeStreamResponse(body))

    file = DistroSourceFile("f.dsc", hashlib.sha256(body).hexdigest())
    pkg = DistroSourcePackage(directory="d", version="1.0-1", files=[file])
    calls: list[tuple[str, int, int]] = []
    download_source_package("http://archive.example", pkg, tmp_path, on_progress=lambda *a: calls.append(a))

    assert calls
    assert calls[-1] == ("f.dsc", 100, 100)


def test_extract_source_package_raises_on_dpkg_source_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResult:
        returncode = 1
        stderr = b"dpkg-source: error: bad patch"

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.subprocess.run", lambda *_a, **_k: FakeResult())

    dsc_path = tmp_path / "linux_1.dsc"
    dsc_path.write_text("fake dsc")

    with pytest.raises(KconfigSubprocessFailedError):
        extract_source_package(dsc_path, tmp_path / "out")
