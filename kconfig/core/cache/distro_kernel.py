from __future__ import annotations

import gzip
import hashlib
import subprocess
import time
from dataclasses import dataclass, field
from email.parser import Parser
from functools import cmp_to_key
from typing import TYPE_CHECKING, Any

import requests

from kconfig.exceptions import KconfigFileInvalidError, KconfigSubprocessFailedError, KconfigSymbolNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

DOWNLOAD_CHUNK_SIZE = 1024 * 1024
"""1 MiB -- these packages routinely include a 200+ MB orig tarball."""


@dataclass
class DistroSourceFile:
    """A single file belonging to a distro source package."""

    name: str
    sha256: str


@dataclass
class DistroSourcePackage:
    """A resolved distro source package: where it lives, and what it's made of."""

    directory: str
    version: str
    files: list[DistroSourceFile] = field(default_factory=list)
    binary: str = ""
    """Raw ``Binary:`` field text -- the binary packages this source produces
    (e.g. ``linux-image-3.2.0-4-amd64, linux-headers-3.2.0-4-amd64, ...``),
    useful for spotting which kernel ABI (``uname -r``) a version corresponds to.
    """

    @property
    def dsc_file(self) -> DistroSourceFile:
        """The ``.dsc`` control file naming (and controlling extraction of) this package."""
        return next(f for f in self.files if f.name.endswith(".dsc"))

    @property
    def image_abis(self) -> list[str]:
        """Kernel ABI names (``uname -r`` style, e.g. ``6.8.0-31-generic``) this package's images produce.

        Pulled from the raw ``Binary:`` field's ``linux-image-*``/
        ``linux-image-unsigned-*`` entries (skipping ``-dbg`` variants) --
        the bridge from a source package version back to the ABI name someone
        actually has on a running system.
        """
        abis = []
        for raw_name in self.binary.split(","):
            name = raw_name.strip()
            for prefix in ("linux-image-unsigned-", "linux-image-"):
                if name.startswith(prefix) and "-dbg" not in name:
                    abis.append(name.removeprefix(prefix))
                    break

        return abis


def _parse_sources_stanza(stanza: str, package: str, version: str | None) -> DistroSourcePackage | None:
    """Parse one Sources-index stanza; return it if it matches, else None.

    ``version=None`` matches any version of ``package`` (used to enumerate
    every version available, e.g. to later pick the newest one).
    """
    fields = Parser().parsestr(stanza)
    stanza_version = fields.get("Version")
    if fields.get("Package") != package or not stanza_version:
        return None
    if version is not None and stanza_version != version:
        return None

    directory = fields.get("Directory")
    checksums = fields.get("Checksums-Sha256")
    if not directory or not checksums:
        raise KconfigFileInvalidError("Sources", f"'{package}' stanza is missing Directory/Checksums-Sha256")

    files = [
        DistroSourceFile(name=name, sha256=sha256)
        for sha256, _size, name in (line.split() for line in checksums.strip().splitlines())
    ]
    binary = fields.get("Binary", "")
    return DistroSourcePackage(directory=directory, version=stanza_version, files=files, binary=binary)


def _iter_matching_packages(
    archive_url: str, pockets: list[str], package: str, version: str | None
) -> list[DistroSourcePackage]:
    found: list[DistroSourcePackage] = []
    for pocket in pockets:
        response = requests.get(f"{archive_url}/dists/{pocket}/main/source/Sources.gz", timeout=(10, 60))
        if response.status_code != requests.codes.ok:
            continue

        sources_text = gzip.decompress(response.content).decode(errors="replace")
        for stanza in sources_text.split("\n\n"):
            if not stanza.strip():
                continue

            match = _parse_sources_stanza(stanza, package, version)
            if match is not None:
                found.append(match)

    return found


def find_source_package(archive_url: str, pockets: list[str], package: str, version: str) -> DistroSourcePackage:
    """Find a distro source package's exact file listing by searching a set of archive pockets.

    Args:
        archive_url (str): Base archive URL (e.g. ``http://archive.ubuntu.com/ubuntu``).
        pockets (list[str]): Pocket/suite names to search, in order (e.g. ``["noble", "noble-updates"]``).
        package (str): Source package name (e.g. ``linux``).
        version (str): Exact package version to match (e.g. ``6.8.0-31.31``).

    Raises:
        KconfigSymbolNotFoundError: No pocket has this exact package/version.

    Returns:
        DistroSourcePackage: The matching package's directory and file listing.

    """
    for pocket in pockets:
        found = _iter_matching_packages(archive_url, [pocket], package, version)
        if found:
            return found[0]

    raise KconfigSymbolNotFoundError(f"{package}={version}", archive_url)


def _dpkg_version_gt(a: str, b: str) -> bool:
    """Whether Debian/Ubuntu version ``a`` is newer than ``b``.

    Shells out to ``dpkg``, which already implements the epoch/upstream/revision
    comparison rules correctly.
    """
    cmd = ["dpkg", "--compare-versions", a, "gt", b]
    return subprocess.run(cmd, check=False, capture_output=True).returncode == 0  # noqa: S603


def _upstream_version(version: str) -> str:
    """Extract a Debian/Ubuntu package version's upstream portion.

    Per Debian Policy, a version is ``[epoch:]upstream_version[-debian_revision]``,
    with the revision (if any) defined as everything after the *last* hyphen.
    """
    version = version.split(":", 1)[-1]
    return version.rsplit("-", 1)[0] if "-" in version else version


def _upstream_matches(candidate_version: str, target: str) -> bool:
    """Whether a package version's upstream portion matches a target kernel.org-style version.

    Debian tracks kernel.org's exact patch level as its upstream version
    (``3.2.78-1``'s upstream is ``3.2.78``), so an exact match covers it. Ubuntu
    instead pins a whole point-release series to ``X.Y.0`` for its entire
    support lifetime regardless of the exact upstream patch level it actually
    tracks (``noble``'s kernel stays ``6.8.0`` across every SRU) -- a
    kernel.org-style ``X.Y.Z`` request should still resolve to that series.
    """
    upstream = _upstream_version(candidate_version)
    if upstream == target:
        return True

    parts = target.split(".")
    return len(parts) >= 2 and upstream == f"{parts[0]}.{parts[1]}.0"


def find_latest_source_package(archive_url: str, pockets: list[str], package: str) -> DistroSourcePackage:
    """Find the newest available version of a source package across a set of archive pockets.

    For when the exact version doesn't matter (or isn't known) -- just "whatever
    this release currently has." Every pocket is searched (unlike
    ``find_source_package``, which stops at the first pocket that has anything),
    since a later pocket in the list (e.g. ``-updates``) isn't guaranteed to be
    newer than an earlier one for every package.

    Raises:
        KconfigSymbolNotFoundError: No pocket has any version of this package.

    Returns:
        DistroSourcePackage: The newest matching package found, by Debian version ordering.

    """
    candidates = _iter_matching_packages(archive_url, pockets, package, version=None)
    if not candidates:
        raise KconfigSymbolNotFoundError(package, archive_url)

    best = candidates[0]
    for candidate in candidates[1:]:
        if _dpkg_version_gt(candidate.version, best.version):
            best = candidate
    return best


def _compare_by_version(a: DistroSourcePackage, b: DistroSourcePackage) -> int:
    if _dpkg_version_gt(a.version, b.version):
        return -1
    if _dpkg_version_gt(b.version, a.version):
        return 1
    return 0


def list_source_packages(archive_url: str, pockets: list[str], package: str) -> list[DistroSourcePackage]:
    """List every distinct version of a source package available across a set of archive pockets.

    For finding out what's actually available (e.g. to match a known kernel
    ABI like ``3.2.0-4`` from ``uname -r`` back to the source package version
    that produced it -- see ``DistroSourcePackage.binary``) rather than
    guessing an exact version up front.

    Returns:
        list[DistroSourcePackage]: Every distinct version found, newest first.

    """
    candidates = _iter_matching_packages(archive_url, pockets, package, version=None)

    seen: set[str] = set()
    unique: list[DistroSourcePackage] = []
    for candidate in candidates:
        if candidate.version not in seen:
            seen.add(candidate.version)
            unique.append(candidate)

    return sorted(unique, key=cmp_to_key(_compare_by_version))


def _verify_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise KconfigFileInvalidError(path, f"sha256 mismatch: expected {expected}, got {digest}")


def _stream_download(
    url: str,
    dest_path: Path,
    on_progress: Callable[[str, int, int], None] | None = None,
    timeout: tuple[int, int] = (10, 60),
    retries: int = 1,
) -> None:
    """Stream a URL to a file, reporting progress via ``on_progress(name, downloaded, total)``.

    ``retries`` (beyond the first attempt) only guards against a failure
    *before* any bytes were written -- a connection/read timeout partway
    through an already-flowing download still propagates immediately rather
    than silently restarting a large, mostly-complete transfer from scratch.
    """
    for attempt in range(retries):
        downloaded = 0
        try:
            with requests.get(url, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))

                # These files (.dsc/.tar.*/.diff.gz/...) are archive-format
                # binaries already, checked byte-for-byte against a known
                # checksum afterward -- ``decode_content = False`` stops
                # `requests`/urllib3 transparently gunzipping a response whose
                # ``Content-Encoding`` claims gzip, which silently hands back
                # the wrong (decompressed-once) bytes for a file that's
                # *already* gzipped on disk. Confirmed for real against
                # Launchpad, where its response caching proxy kept serving a
                # gzip-transport-encoded response regardless of the request's
                # own ``Accept-Encoding`` -- so this has to be handled on read,
                # not avoided by asking the server not to encode it.
                response.raw.decode_content = False

                with dest_path.open("wb") as f:
                    while chunk := response.raw.read(DOWNLOAD_CHUNK_SIZE):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress:
                            on_progress(dest_path.name, downloaded, total_size)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if downloaded > 0 or attempt == retries - 1:
                raise
            time.sleep(2**attempt)
        else:
            return


def download_source_package(
    archive_url: str,
    pkg: DistroSourcePackage,
    dest_dir: Path,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> Path:
    """Download every file in a source package's listing, verifying each against its checksum.

    Args:
        archive_url (str): Base archive URL the package's ``directory`` is relative to.
        pkg (DistroSourcePackage): The package to download (from ``find_source_package``).
        dest_dir (Path): Directory to download every file into.
        on_progress (Callable[[str, int, int], None] | None): Optional callback,
            invoked as ``(filename, downloaded_bytes, total_bytes)`` while streaming.

    Returns:
        Path: The path to the downloaded ``.dsc`` file.

    """
    for file in pkg.files:
        dest_path = dest_dir / file.name
        _stream_download(f"{archive_url}/{pkg.directory}/{file.name}", dest_path, on_progress)
        _verify_sha256(dest_path, file.sha256)

    return dest_dir / pkg.dsc_file.name


# --- snapshot.debian.org -- Debian's permanent, full-history package archive --

SNAPSHOT_BASE_URL = "https://snapshot.debian.org"
"""Every version of every Debian source package ever archived, addressed by
content hash rather than a release's current pocket contents -- unlike
``find_source_package``/``find_latest_source_package`` above (which only see
whatever a release's *live* mirror currently has), this can resolve an exact
historical upstream version without needing to already know which Debian
release (if any still has it) shipped it."""


def _snapshot_get(path: str) -> Any:
    response = requests.get(f"{SNAPSHOT_BASE_URL}{path}", timeout=(10, 60))
    response.raise_for_status()
    return response.json()


def find_snapshot_package(package: str, upstream_version: str) -> str:
    """Find the newest snapshot.debian.org version of ``package`` matching an upstream kernel version.

    Args:
        package (str): Source package name (e.g. ``linux``).
        upstream_version (str): Upstream kernel version to match (e.g. ``3.2.78``).

    Raises:
        KconfigSymbolNotFoundError: No archived version matches.

    Returns:
        str: The newest matching full package version (e.g. ``3.2.78-1``).

    """
    data = _snapshot_get(f"/mr/package/{package}/")
    candidates: list[str] = [
        r["version"] for r in data.get("result", []) if _upstream_matches(r["version"], upstream_version)
    ]
    if not candidates:
        raise KconfigSymbolNotFoundError(f"{package} (upstream {upstream_version})", SNAPSHOT_BASE_URL)

    best = candidates[0]
    for candidate in candidates[1:]:
        if _dpkg_version_gt(candidate, best):
            best = candidate
    return best


def download_snapshot_package(
    package: str, version: str, dest_dir: Path, on_progress: Callable[[str, int, int], None] | None = None
) -> Path:
    """Download every file belonging to a snapshot.debian.org package version.

    snapshot.debian.org addresses files by content hash rather than a
    ``directory``+filename pair, so each file is downloaded from
    ``/file/<hash>`` and verified against that same hash directly -- the URL
    *is* the checksum, unlike ``download_source_package``'s separately-parsed
    ``Checksums-Sha256`` field.

    Returns:
        Path: The path to the downloaded ``.dsc`` file.

    Raises:
        KconfigFileInvalidError: A downloaded file's content doesn't hash to
            the identifier it was fetched by, or no ``.dsc`` was listed.

    """
    data = _snapshot_get(f"/mr/package/{package}/{version}/srcfiles?fileinfo=1")

    dsc_path: Path | None = None
    for entry in data["result"]:
        file_hash = entry["hash"]
        name = data["fileinfo"][file_hash][0]["name"]
        dest_path = dest_dir / name

        _stream_download(f"{SNAPSHOT_BASE_URL}/file/{file_hash}", dest_path, on_progress)
        # Matching snapshot.debian.org's own file-identity hash for integrity,
        # not a security boundary.
        digest = hashlib.sha1(dest_path.read_bytes()).hexdigest()  # noqa: S324
        if digest != file_hash:
            raise KconfigFileInvalidError(dest_path, f"sha1 mismatch: expected {file_hash}, got {digest}")

        if name.endswith(".dsc"):
            dsc_path = dest_path

    if dsc_path is None:
        raise KconfigFileInvalidError(f"{package}={version}", "srcfiles listing had no .dsc file")

    return dsc_path


# --- Launchpad -- Ubuntu's equivalent full-history archive --

LAUNCHPAD_ARCHIVE_API = "https://api.launchpad.net/1.0/ubuntu/+archive/primary"
"""Ubuntu has no byte-identical equivalent of snapshot.debian.org, but
Launchpad's publishing history serves the same purpose: it keeps every source
package version ever published across every series and pocket (not just a
release's current live contents), and its per-file download links
(``sourceFileUrls``) are permanent librarian storage, not tied to whatever a
release's archive happens to contain today."""


LAUNCHPAD_TIMEOUT = (20, 90)
"""Launchpad's own connection setup is noticeably slower than the plain
archive mirrors elsewhere in this module (confirmed for real: a cold
connection to launchpad.net routinely took >10s just to establish, before any
data transfer) -- a longer connect timeout avoids spurious failures on an
otherwise-working, if slow, connection."""


LAUNCHPAD_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
"""A full history scan is dozens of sequential requests (see
``find_launchpad_package``); Launchpad returning a transient 5xx/429, or an
outright connection/read timeout, partway through one (both confirmed for
real) shouldn't fail the whole lookup."""

LAUNCHPAD_MAX_RETRIES = 4


def _launchpad_get(url: str) -> Any:
    for attempt in range(LAUNCHPAD_MAX_RETRIES):
        try:
            response = requests.get(url, timeout=LAUNCHPAD_TIMEOUT)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == LAUNCHPAD_MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)
            continue

        if response.status_code in LAUNCHPAD_TRANSIENT_STATUS_CODES and attempt < LAUNCHPAD_MAX_RETRIES - 1:
            time.sleep(2**attempt)
            continue
        response.raise_for_status()
        return response.json()
    raise AssertionError  # pragma: no cover -- the loop above always returns or raises


def find_launchpad_package(package: str, upstream_version: str) -> tuple[str, str]:
    """Find the newest Launchpad-published version of ``package`` matching an upstream kernel version.

    Every publication of ``package`` (across every series/pocket, from warty
    onward) is paginated through -- Launchpad has no server-side filter for
    "upstream portion of the version", only an exact full-version match, so
    there's no way to narrow this server-side the way ``find_snapshot_package``
    can. Slow (a full scan can be dozens of requests), but a one-time
    discovery cost, same as ``search-ubuntu``/``search-debian``.

    Args:
        package (str): Source package name (e.g. ``linux``).
        upstream_version (str): Upstream kernel version to match (e.g. ``6.8.0``).

    Raises:
        KconfigSymbolNotFoundError: No published version matches.

    Returns:
        tuple[str, str]: ``(version, self_link)`` of the newest match --
            ``self_link`` is what ``download_launchpad_package`` needs.

    """
    url = f"{LAUNCHPAD_ARCHIVE_API}?ws.op=getPublishedSources&source_name={package}&exact_match=true&ws.size=300"
    best: tuple[str, str] | None = None
    while url:
        data = _launchpad_get(url)
        for entry in data["entries"]:
            version = entry["source_package_version"]
            if _upstream_matches(version, upstream_version) and (best is None or _dpkg_version_gt(version, best[0])):
                best = (version, entry["self_link"])
        url = data.get("next_collection_link")

    if best is None:
        raise KconfigSymbolNotFoundError(f"{package} (upstream {upstream_version})", LAUNCHPAD_ARCHIVE_API)

    return best


def _parse_dsc_checksums(dsc_text: str) -> dict[str, str]:
    """Parse a ``.dsc`` control file's own ``Checksums-Sha256`` field into ``{filename: sha256}``.

    A ``.dsc`` served straight from an archive is always PGP clearsigned
    (``-----BEGIN PGP SIGNED MESSAGE-----`` armor wrapping the actual control
    fields) -- stripped here rather than verified, since the goal is content
    integrity (did the download actually match what the ``.dsc`` itself
    claims), not authenticity.
    """
    if dsc_text.startswith("-----BEGIN PGP SIGNED MESSAGE-----"):
        _, _, body = dsc_text.partition("\n\n")
        dsc_text, _, _ = body.partition("-----BEGIN PGP SIGNATURE-----")

    checksums = Parser().parsestr(dsc_text).get("Checksums-Sha256", "")
    return {name: sha256 for sha256, _size, name in (line.split() for line in checksums.strip().splitlines())}


def download_launchpad_package(
    self_link: str, dest_dir: Path, on_progress: Callable[[str, int, int], None] | None = None
) -> Path:
    """Download every file belonging to a Launchpad-published source package.

    Every downloaded sibling file is verified against the SHA256 the ``.dsc``
    itself declares for it (parsed after every file is downloaded, since the
    ``.dsc`` is one of the files being fetched) -- confirmed for real to
    matter: a Launchpad download intermittently came back with the wrong
    *size* of content for a file with no error raised anywhere in the
    request, which silently corrupted the tree until ``dpkg-source`` failed
    much later with a confusing error.

    Args:
        self_link (str): A publication's ``self_link``, from ``find_launchpad_package``.
        dest_dir (Path): Directory to download every file into.
        on_progress (Callable[[str, int, int], None] | None): Optional callback,
            invoked as ``(filename, downloaded_bytes, total_bytes)`` while streaming.

    Returns:
        Path: The path to the downloaded ``.dsc`` file.

    Raises:
        KconfigFileInvalidError: No ``.dsc`` file was listed, or a downloaded
            file doesn't match the checksum the ``.dsc`` declares for it.

    """
    dsc_path: Path | None = None
    for url in _launchpad_get(f"{self_link}?ws.op=sourceFileUrls"):
        dest_path = dest_dir / url.rsplit("/", 1)[-1]
        _stream_download(url, dest_path, on_progress, timeout=LAUNCHPAD_TIMEOUT, retries=LAUNCHPAD_MAX_RETRIES)
        if dest_path.name.endswith(".dsc"):
            dsc_path = dest_path

    if dsc_path is None:
        raise KconfigFileInvalidError(self_link, "sourceFileUrls listing had no .dsc file")

    for name, sha256 in _parse_dsc_checksums(dsc_path.read_text(errors="replace")).items():
        file_path = dest_dir / name
        if file_path.exists():
            _verify_sha256(file_path, sha256)

    return dsc_path


def extract_source_package(dsc_path: Path, dest_dir: Path) -> None:
    """Unpack a distro source package, applying its patches, via ``dpkg-source -x``.

    Args:
        dsc_path (Path): Path to the downloaded ``.dsc`` file (its sibling
            files -- orig tarball, diff/debian tarball -- must be alongside it).
        dest_dir (Path): Directory the fully patched source tree should land in.

    Raises:
        KconfigSubprocessFailedError: ``dpkg-source`` exited non-zero.

    """
    cmd = ["dpkg-source", "-x", str(dsc_path), str(dest_dir)]
    result = subprocess.run(cmd, cwd=dsc_path.parent, check=False, capture_output=True)  # noqa: S603
    if result.returncode != 0:
        raise KconfigSubprocessFailedError("dpkg-source", result.stderr.decode(errors="replace"))
