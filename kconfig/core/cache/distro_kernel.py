from __future__ import annotations

import gzip
import hashlib
import subprocess
from dataclasses import dataclass, field
from email.parser import Parser
from functools import cmp_to_key
from typing import TYPE_CHECKING

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
        url = f"{archive_url}/{pkg.directory}/{file.name}"

        with requests.get(url, stream=True, timeout=(10, 60)) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))

            downloaded = 0
            with dest_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        on_progress(file.name, downloaded, total_size)

        _verify_sha256(dest_path, file.sha256)

    return dest_dir / pkg.dsc_file.name


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
