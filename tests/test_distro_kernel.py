from __future__ import annotations

import gzip
import hashlib
from typing import TYPE_CHECKING, Self

import pytest
import requests

from kconfig.core.cache.distro_kernel import (
    DistroSourceFile,
    DistroSourcePackage,
    _launchpad_get,
    download_launchpad_package,
    download_snapshot_package,
    download_source_package,
    extract_source_package,
    find_latest_source_package,
    find_launchpad_package,
    find_snapshot_package,
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


def test_image_abis_extracts_only_image_binaries() -> None:
    pkg = DistroSourcePackage(
        directory="pool/main/l/linux",
        version="6.8.0-31.31",
        binary=(
            "linux-image-6.8.0-31-generic, linux-image-unsigned-6.8.0-31-generic, "
            "linux-headers-6.8.0-31-generic, linux-image-6.8.0-31-generic-dbgsym"
        ),
    )

    assert pkg.image_abis == ["6.8.0-31-generic", "6.8.0-31-generic"]


def test_image_abis_empty_when_no_binary_field() -> None:
    pkg = DistroSourcePackage(directory="pool/main/l/linux", version="1.0-1")
    assert pkg.image_abis == []


class _FakeRaw:
    """Stands in for ``requests.Response.raw`` -- a stateful, chunked ``read()``."""

    def __init__(self, body: bytes) -> None:
        self._body = body
        self._pos = 0
        self.decode_content = True  # mirrors the real attribute's default

    def read(self, chunk_size: int) -> bytes:
        chunk = self._body[self._pos : self._pos + chunk_size]
        self._pos += len(chunk)
        return chunk


class _FakeStreamResponse:
    """Stands in for ``requests.get(..., stream=True)``'s context-manager interface."""

    def __init__(self, body: bytes) -> None:
        self._body = body
        self.headers = {"content-length": str(len(body))}
        self.raw = _FakeRaw(body)

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


HTTP_ERROR_THRESHOLD = 400


class _FakeJSONResponse:
    """Stands in for a plain (non-streaming) JSON ``requests.get(...)`` call."""

    def __init__(self, data: object, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= HTTP_ERROR_THRESHOLD:
            raise requests.exceptions.HTTPError(f"{self.status_code} error")

    def json(self) -> object:
        return self._data


# --- snapshot.debian.org ----------------------------------------------------


def test_find_snapshot_package_matches_exact_upstream_version(monkeypatch: pytest.MonkeyPatch) -> None:
    data = {"result": [{"version": "3.2.78-1"}, {"version": "3.2.79-1"}, {"version": "3.16.7-ckt25-1"}]}
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", lambda *_a, **_k: _FakeJSONResponse(data))

    assert find_snapshot_package("linux", "3.2.78") == "3.2.78-1"


def test_find_snapshot_package_picks_newest_revision_when_several_match(monkeypatch: pytest.MonkeyPatch) -> None:
    data = {"result": [{"version": "3.2.78-1"}, {"version": "3.2.78-2"}]}
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", lambda *_a, **_k: _FakeJSONResponse(data))

    assert find_snapshot_package("linux", "3.2.78") == "3.2.78-2"


def test_find_snapshot_package_raises_when_no_upstream_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    data = {"result": [{"version": "3.2.79-1"}]}
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", lambda *_a, **_k: _FakeJSONResponse(data))

    with pytest.raises(KconfigSymbolNotFoundError):
        find_snapshot_package("linux", "3.2.78")


def test_download_snapshot_package_downloads_and_verifies_by_content_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dsc_body = b"pretend .dsc contents"
    dsc_hash = hashlib.sha1(dsc_body).hexdigest()  # noqa: S324
    orig_body = b"pretend orig tarball"
    orig_hash = hashlib.sha1(orig_body).hexdigest()  # noqa: S324

    srcfiles = {
        "result": [{"hash": dsc_hash}, {"hash": orig_hash}],
        "fileinfo": {
            dsc_hash: [{"name": "linux_3.2.78-1.dsc"}],
            orig_hash: [{"name": "linux_3.2.78.orig.tar.xz"}],
        },
    }

    def fake_get(url: str, **_kwargs: object) -> object:
        if url.endswith("/srcfiles?fileinfo=1"):
            return _FakeJSONResponse(srcfiles)
        if url.endswith(f"/file/{dsc_hash}"):
            return _FakeStreamResponse(dsc_body)
        if url.endswith(f"/file/{orig_hash}"):
            return _FakeStreamResponse(orig_body)
        raise AssertionError(url)

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    dsc_path = download_snapshot_package("linux", "3.2.78-1", tmp_path)
    assert dsc_path == tmp_path / "linux_3.2.78-1.dsc"
    assert dsc_path.read_bytes() == dsc_body
    assert (tmp_path / "linux_3.2.78.orig.tar.xz").read_bytes() == orig_body


def test_download_snapshot_package_rejects_content_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = b"actual content"
    claimed_hash = "0" * 40  # doesn't match sha1(body)
    srcfiles = {"result": [{"hash": claimed_hash}], "fileinfo": {claimed_hash: [{"name": "linux_1-1.dsc"}]}}

    def fake_get(url: str, **_kwargs: object) -> object:
        if url.endswith("/srcfiles?fileinfo=1"):
            return _FakeJSONResponse(srcfiles)
        return _FakeStreamResponse(body)

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    with pytest.raises(KconfigFileInvalidError):
        download_snapshot_package("linux", "1-1", tmp_path)


def test_download_snapshot_package_raises_when_no_dsc_listed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = b"tarball only"
    file_hash = hashlib.sha1(body).hexdigest()  # noqa: S324
    srcfiles = {"result": [{"hash": file_hash}], "fileinfo": {file_hash: [{"name": "linux_1-1.orig.tar.xz"}]}}

    def fake_get(url: str, **_kwargs: object) -> object:
        if url.endswith("/srcfiles?fileinfo=1"):
            return _FakeJSONResponse(srcfiles)
        return _FakeStreamResponse(body)

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    with pytest.raises(KconfigFileInvalidError):
        download_snapshot_package("linux", "1-1", tmp_path)


# --- Launchpad ---------------------------------------------------------------


def test_launchpad_get_retries_transient_errors_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.time.sleep", lambda _seconds: None)

    responses = iter(
        [
            _FakeJSONResponse(None, status_code=503),
            _FakeJSONResponse(None, status_code=429),
            _FakeJSONResponse({"ok": True}),
        ]
    )
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", lambda *_a, **_k: next(responses))

    assert _launchpad_get("https://api.launchpad.net/x") == {"ok": True}


def test_launchpad_get_retries_connection_timeouts_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.time.sleep", lambda _seconds: None)

    responses = iter([requests.exceptions.ReadTimeout("timed out"), _FakeJSONResponse({"ok": True})])

    def fake_get(*_a: object, **_k: object) -> object:
        next_response = next(responses)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    assert _launchpad_get("https://api.launchpad.net/x") == {"ok": True}


def test_launchpad_get_raises_after_exhausting_connection_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.time.sleep", lambda _seconds: None)

    def fake_get(*_a: object, **_k: object) -> object:
        raise requests.exceptions.ReadTimeout("timed out")

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    with pytest.raises(requests.exceptions.ReadTimeout):
        _launchpad_get("https://api.launchpad.net/x")


def test_launchpad_get_raises_after_exhausting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        "kconfig.core.cache.distro_kernel.requests.get", lambda *_a, **_k: _FakeJSONResponse(None, status_code=503)
    )

    with pytest.raises(requests.exceptions.HTTPError, match="503"):
        _launchpad_get("https://api.launchpad.net/x")


def test_find_launchpad_package_matches_exact_upstream_and_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    page1 = {
        "entries": [{"source_package_version": "6.8.0-137.137", "self_link": "https://api.launchpad.net/x/1"}],
        "next_collection_link": "https://api.launchpad.net/x?memo=page2",
    }
    page2 = {"entries": [{"source_package_version": "5.15.0-187.197", "self_link": "https://api.launchpad.net/x/2"}]}

    def fake_get(url: str, **_kwargs: object) -> object:
        return _FakeJSONResponse(page2 if "page2" in url else page1)

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    version, self_link = find_launchpad_package("linux", "6.8.0")
    assert version == "6.8.0-137.137"
    assert self_link == "https://api.launchpad.net/x/1"


def test_find_launchpad_package_picks_newest_when_several_series_match(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ubuntu pins upstream to "6.8.0" for a whole series' lifetime -- both of
    # these are genuinely different, valid matches; the newest must win.
    page = {
        "entries": [
            {"source_package_version": "6.8.0-31.31", "self_link": "https://api.launchpad.net/x/old"},
            {"source_package_version": "6.8.0-137.137", "self_link": "https://api.launchpad.net/x/new"},
        ]
    }
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", lambda *_a, **_k: _FakeJSONResponse(page))

    version, self_link = find_launchpad_package("linux", "6.8.0")
    assert version == "6.8.0-137.137"
    assert self_link == "https://api.launchpad.net/x/new"


def test_find_launchpad_package_matches_ubuntu_majorminor_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    # A kernel.org-style patch level ("6.8.5") should still resolve to the
    # Ubuntu series pinned at "6.8.0", since Ubuntu never bumps upstream past
    # the ".0" for a series regardless of which patch level it tracks.
    page = {"entries": [{"source_package_version": "6.8.0-137.137", "self_link": "https://api.launchpad.net/x/1"}]}
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", lambda *_a, **_k: _FakeJSONResponse(page))

    version, _self_link = find_launchpad_package("linux", "6.8.5")
    assert version == "6.8.0-137.137"


def test_find_launchpad_package_raises_when_no_upstream_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    page = {"entries": [{"source_package_version": "5.15.0-187.197", "self_link": "https://api.launchpad.net/x/1"}]}
    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", lambda *_a, **_k: _FakeJSONResponse(page))

    with pytest.raises(KconfigSymbolNotFoundError):
        find_launchpad_package("linux", "6.8.0")


def test_download_launchpad_package_downloads_every_source_file_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dsc_body = b"pretend dsc"
    orig_body = b"pretend orig"
    urls = [
        "https://launchpadlibrarian.net/x/linux_1-1.dsc",
        "https://launchpadlibrarian.net/x/linux_1.orig.tar.gz",
    ]

    def fake_get(url: str, **_kwargs: object) -> object:
        if url.endswith("ws.op=sourceFileUrls"):
            return _FakeJSONResponse(urls)
        if url.endswith("linux_1-1.dsc"):
            return _FakeStreamResponse(dsc_body)
        return _FakeStreamResponse(orig_body)

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    dsc_path = download_launchpad_package("https://api.launchpad.net/x/+sourcepub/1", tmp_path)
    assert dsc_path == tmp_path / "linux_1-1.dsc"
    assert dsc_path.read_bytes() == dsc_body
    assert (tmp_path / "linux_1.orig.tar.gz").read_bytes() == orig_body


def test_download_launchpad_package_verifies_against_dsc_checksums(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orig_body = b"pretend orig tarball"
    orig_sha256 = hashlib.sha256(orig_body).hexdigest()
    dsc_body = (
        b"-----BEGIN PGP SIGNED MESSAGE-----\n"
        b"Hash: SHA512\n\n"
        b"Source: linux\n"
        b"Version: 1-1\n"
        b"Checksums-Sha256:\n"
        b" " + orig_sha256.encode() + b" 20 linux_1.orig.tar.gz\n\n"
        b"-----BEGIN PGP SIGNATURE-----\nfake\n-----END PGP SIGNATURE-----\n"
    )
    urls = [
        "https://launchpadlibrarian.net/x/linux_1-1.dsc",
        "https://launchpadlibrarian.net/x/linux_1.orig.tar.gz",
    ]

    def fake_get(url: str, **_kwargs: object) -> object:
        if url.endswith("ws.op=sourceFileUrls"):
            return _FakeJSONResponse(urls)
        if url.endswith("linux_1-1.dsc"):
            return _FakeStreamResponse(dsc_body)
        return _FakeStreamResponse(orig_body)

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    dsc_path = download_launchpad_package("https://api.launchpad.net/x/+sourcepub/1", tmp_path)
    assert dsc_path.read_bytes() == dsc_body


def test_download_launchpad_package_rejects_dsc_checksum_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The .dsc claims a checksum that doesn't match what actually gets
    # downloaded for the sibling file -- simulates the real corrupted-transfer
    # failure this verification step exists to catch.
    wrong_sha256 = "0" * 64
    dsc_body = (
        b"-----BEGIN PGP SIGNED MESSAGE-----\n"
        b"Hash: SHA512\n\n"
        b"Source: linux\n"
        b"Version: 1-1\n"
        b"Checksums-Sha256:\n"
        b" " + wrong_sha256.encode() + b" 20 linux_1.orig.tar.gz\n\n"
        b"-----BEGIN PGP SIGNATURE-----\nfake\n-----END PGP SIGNATURE-----\n"
    )
    urls = [
        "https://launchpadlibrarian.net/x/linux_1-1.dsc",
        "https://launchpadlibrarian.net/x/linux_1.orig.tar.gz",
    ]

    def fake_get(url: str, **_kwargs: object) -> object:
        if url.endswith("ws.op=sourceFileUrls"):
            return _FakeJSONResponse(urls)
        if url.endswith("linux_1-1.dsc"):
            return _FakeStreamResponse(dsc_body)
        return _FakeStreamResponse(b"pretend orig tarball")

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    with pytest.raises(KconfigFileInvalidError):
        download_launchpad_package("https://api.launchpad.net/x/+sourcepub/1", tmp_path)


def test_download_launchpad_package_raises_when_no_dsc_listed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    urls = ["https://launchpadlibrarian.net/x/linux_1.orig.tar.gz"]

    def fake_get(url: str, **_kwargs: object) -> object:
        if url.endswith("ws.op=sourceFileUrls"):
            return _FakeJSONResponse(urls)
        return _FakeStreamResponse(b"data")

    monkeypatch.setattr("kconfig.core.cache.distro_kernel.requests.get", fake_get)

    with pytest.raises(KconfigFileInvalidError):
        download_launchpad_package("https://api.launchpad.net/x/+sourcepub/1", tmp_path)
