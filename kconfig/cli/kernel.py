from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import requests
import typer
from rich.progress import BarColumn, DownloadColumn, Progress, SpinnerColumn, TextColumn, TransferSpeedColumn

from kconfig.control_api import (
    CACHE_KERNEL_DIR,
    download_source_package,
    extract_source_package,
    find_latest_source_package,
    find_source_package,
    list_source_packages,
)
from kconfig.exceptions import KconfigFileInvalidError, KconfigSubprocessFailedError, KconfigSymbolNotFoundError
from kconfig.styling_api import render_distro_package_table, render_distro_search_table, render_kernel_version_table, ui

if TYPE_CHECKING:
    from kconfig.core.cache.distro_kernel import DistroSourcePackage

app = typer.Typer()

UBUNTU_ARCHIVE = "http://archive.ubuntu.com/ubuntu"
# Debian releases eventually move off the live mirror to the historical archive
# (e.g. wheezy/Debian 7) -- try the live one first, then fall back.
DEBIAN_ARCHIVES = ["http://deb.debian.org/debian", "http://archive.debian.org/debian"]
# Debian has no equivalent of Ubuntu's meta-release listing, so the codenames
# to search are hardcoded -- newest first, stable and rarely changing.
DEBIAN_CODENAMES = [
    "trixie",
    "bookworm",
    "bullseye",
    "buster",
    "stretch",
    "jessie",
    "wheezy",
    "squeeze",
    "lenny",
    "etch",
]


def _make_download_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        transient=True,
    )


def kernel_tarball_urls(version: str) -> list[str]:
    """Return kernel.org tarball URLs for ``version``, newest-compatible form first."""
    major = version.split(".", maxsplit=1)[0]
    urls = [f"https://cdn.kernel.org/pub/linux/kernel/v{major}.x/linux-{version}.tar.xz"]
    # kernel.org names an initial release `linux-X.Y.tar.xz`; only patch releases
    # get a third component. Try the exact form first, then the initial-release form.
    if version.endswith(".0"):
        urls.append(f"https://cdn.kernel.org/pub/linux/kernel/v{major}.x/linux-{version[:-2]}.tar.xz")
    return urls


@app.command("list")
def kernel_list() -> None:
    """List the available cached kernels."""
    versions = [p.name.replace("linux-", "") for p in CACHE_KERNEL_DIR.glob("linux-*") if p.is_dir()]

    def version_sort(v: str) -> list[int]:
        try:
            return [int(p) for p in v.split(".")]
        except ValueError:
            return [0]

    render_kernel_version_table(sorted(versions, key=version_sort, reverse=True), CACHE_KERNEL_DIR)


@app.command("fetch")
def kernel_fetch(
    version: Annotated[str, typer.Argument(help="Linux kernel version to fetch.")],
) -> None:
    """Fetch a kernel from Linux."""
    ui.out_info(f"Fetching Kernel: {version}")

    urls = kernel_tarball_urls(version)
    extract_dir = CACHE_KERNEL_DIR / f"linux-{version}"
    if extract_dir.exists():
        ui.out_info(f"Kernel {version} is already cached at {extract_dir}")
        return

    tarball_path = CACHE_KERNEL_DIR / f"linux-{version}.tar.xz"
    try:
        for url in urls:
            # Get the file from the URL.
            tarball_path = CACHE_KERNEL_DIR / url.rsplit("/", 1)[-1]
            with requests.get(url, stream=True, timeout=(10, 60)) as r:
                if r.status_code == 404 and url != urls[-1]:
                    ui.out_info(f"Version {version} not found at {url}; trying initial-release name.")
                    continue
                r.raise_for_status()
                total_size = int(r.headers.get("content-length", 0))

                with tarball_path.open("wb") as f, _make_download_progress() as progress:
                    task = progress.add_task(f"Downloading {tarball_path.name}...", total=total_size)
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))

            ui.out_info("Extracting tarball...")
            with tarfile.open(tarball_path, "r:xz") as tar:
                tar.extractall(path=CACHE_KERNEL_DIR)  # noqa: S202

            tarball_path.unlink()
            source_dir = CACHE_KERNEL_DIR / tarball_path.name.removesuffix(".tar.xz")
            if source_dir.exists() and not extract_dir.exists():
                source_dir.rename(extract_dir)
            break

        ui.out_success(f"Kernel {version} ready at {extract_dir}")
    except requests.exceptions.ReadTimeout as e:
        ui.out_error("Download timed out. The kernel.org mirror was too slow.")
        if tarball_path.exists():
            tarball_path.unlink()
        raise typer.Exit(1) from e

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else None
        if status_code == 404:
            ui.out_error(f"Version {version} not found.")
        else:
            ui.out_error(f"Failed to download: {e}")
        raise typer.Exit(1) from e


def _fetch_ubuntu_releases() -> list[tuple[str, str]]:
    """Every ``(codename, version)`` pair from Ubuntu's meta-release listing.

    Covers every release back to warty/04.10, not just currently-supported
    ones -- confirmed when this was first built.
    """
    response = requests.get("https://changelogs.ubuntu.com/meta-release", timeout=(10, 30))
    response.raise_for_status()

    releases = []
    for block in response.text.split("\n\n"):
        dist = version = None
        for line in block.splitlines():
            if line.startswith("Dist:"):
                dist = line.removeprefix("Dist:").strip()
            elif line.startswith("Version:"):
                version = line.removeprefix("Version:").strip().split()[0]

        if dist and version:
            releases.append((dist, version))

    return releases


def _resolve_ubuntu_codename(release: str) -> str:
    """Accept either an Ubuntu codename (``noble``) or version number (``24.04``)."""
    if not any(ch.isdigit() for ch in release):
        return release

    for dist, version in _fetch_ubuntu_releases():
        if version.startswith(release):
            return dist

    raise KconfigSymbolNotFoundError(release, "changelogs.ubuntu.com/meta-release")


def _list_ubuntu_codenames() -> list[str]:
    """Every known Ubuntu codename, for searching across all of them at once."""
    return [dist for dist, _version in _fetch_ubuntu_releases()]


def _try_find_package(
    archive_url: str, pockets: list[str], package: str, version: str | None
) -> DistroSourcePackage | None:
    try:
        if version is not None:
            return find_source_package(archive_url, pockets, package, version)
        return find_latest_source_package(archive_url, pockets, package)
    except KconfigSymbolNotFoundError:
        return None


def _find_distro_package(
    archive_urls: list[str], pockets: list[str], package: str, version: str | None
) -> tuple[str, DistroSourcePackage] | None:
    """Search each archive (in order) for a package, returning (archive_used, package)."""
    for archive_url in archive_urls:
        pkg = _try_find_package(archive_url, pockets, package, version)
        if pkg is not None:
            return archive_url, pkg

    return None


def _list_distro_packages(archive_urls: list[str], pockets: list[str], package: str) -> list[DistroSourcePackage]:
    """Search each archive (in order), returning the first one with any results."""
    for archive_url in archive_urls:
        found = list_source_packages(archive_url, pockets, package)
        if found:
            return found

    return []


def _fetch_distro_source(archive_urls: list[str], pockets: list[str], package: str, version: str | None) -> None:
    """Shared ``fetch-ubuntu``/``fetch-debian`` implementation.

    Downloads the real, patched distro source for a package (exact ``version``,
    or the newest available if ``None``) and extracts it to
    ``CACHE_KERNEL_DIR / f"linux-{version}"`` -- the same convention `fetch`
    already uses, so every existing command's ``-k <version>`` works
    immediately with no further changes.
    """
    ui.out_info(f"Looking up {package}={version or 'latest'} in {', '.join(pockets)} ...")
    found = _find_distro_package(archive_urls, pockets, package, version)
    if found is None:
        ui.out_error(f"Could not find {package}={version or 'any version'} in {', '.join(pockets)}.")
        raise typer.Exit(1)
    archive_url, pkg = found

    extract_dir = CACHE_KERNEL_DIR / f"linux-{pkg.version}"
    if extract_dir.exists():
        ui.out_info(f"Kernel {pkg.version} is already cached at {extract_dir}")
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        with _make_download_progress() as progress:
            task = progress.add_task("Downloading...", total=None)

            def on_progress(filename: str, downloaded: int, total: int) -> None:
                progress.update(task, total=total, completed=downloaded, description=f"Downloading {filename}...")

            try:
                dsc_path = download_source_package(archive_url, pkg, tmp_path, on_progress=on_progress)
            except (requests.exceptions.RequestException, KconfigFileInvalidError) as e:
                ui.out_error(f"Download failed: {e}")
                raise typer.Exit(1) from e

        ui.out_info("Unpacking and applying patches (dpkg-source) ...")
        try:
            extract_source_package(dsc_path, extract_dir)
        except KconfigSubprocessFailedError as e:
            ui.out_error(str(e))
            raise typer.Exit(1) from e

    ui.out_success(f"Kernel {package}={pkg.version} ready at {extract_dir} -- use -k {pkg.version}")


@app.command("fetch-ubuntu")
def kernel_fetch_ubuntu(
    version: Annotated[
        str | None,
        typer.Argument(help="Exact Ubuntu kernel package version, e.g. 6.8.0-31.31. Omit for the latest available."),
    ] = None,
    release: Annotated[
        str, typer.Option("-r", "--release", help="Ubuntu release codename or version, e.g. noble or 24.04.")
    ] = "noble",
    package: Annotated[str, typer.Option("-p", "--package", help="Source package name.")] = "linux",
) -> None:
    """Fetch the real Canonical-patched Ubuntu kernel source for a specific build.

    Unlike ``fetch``, which only gets vanilla kernel.org source, this pulls the
    actual patched tree a given Ubuntu kernel was built from -- needed to
    correctly analyze a real Ubuntu vmlinux/module (distro kernels carry
    extensive patches on top of their nominal upstream version).
    """
    codename = _resolve_ubuntu_codename(release)
    pockets = [codename, f"{codename}-updates", f"{codename}-security"]
    _fetch_distro_source([UBUNTU_ARCHIVE], pockets, package, version)


@app.command("list-ubuntu")
def kernel_list_ubuntu(
    release: Annotated[
        str, typer.Option("-r", "--release", help="Ubuntu release codename or version, e.g. noble or 24.04.")
    ] = "noble",
    package: Annotated[str, typer.Option("-p", "--package", help="Source package name.")] = "linux",
) -> None:
    """List available Ubuntu kernel source package versions for a release.

    Useful for matching a known kernel ABI (``uname -r``, e.g.
    ``6.8.0-31-generic``) back to the exact source package version needed by
    ``fetch-ubuntu``.
    """
    codename = _resolve_ubuntu_codename(release)
    pockets = [codename, f"{codename}-updates", f"{codename}-security"]
    render_distro_package_table(_list_distro_packages([UBUNTU_ARCHIVE], pockets, package))


@app.command("fetch-debian")
def kernel_fetch_debian(
    version: Annotated[
        str | None,
        typer.Argument(
            help="Exact Debian kernel package version, e.g. 3.2.68-1+deb7u2. Omit for the latest available."
        ),
    ] = None,
    release: Annotated[
        str, typer.Option("-r", "--release", help="Debian release codename, e.g. wheezy or bookworm.")
    ] = "bookworm",
    package: Annotated[str, typer.Option("-p", "--package", help="Source package name.")] = "linux",
) -> None:
    """Fetch the real Debian-patched kernel source for a specific build.

    Same idea as ``fetch-ubuntu``, for Debian. Old, no-longer-current releases
    (e.g. wheezy/Debian 7) have moved off the live mirror to
    archive.debian.org -- both are tried automatically.
    """
    pockets = [release, f"{release}-updates", f"{release}-security"]
    _fetch_distro_source(DEBIAN_ARCHIVES, pockets, package, version)


@app.command("list-debian")
def kernel_list_debian(
    release: Annotated[
        str, typer.Option("-r", "--release", help="Debian release codename, e.g. wheezy or bookworm.")
    ] = "bookworm",
    package: Annotated[str, typer.Option("-p", "--package", help="Source package name.")] = "linux",
) -> None:
    """List available Debian kernel source package versions for a release.

    Useful for matching a known kernel ABI (``uname -r``, e.g.
    ``3.2.0-4-amd64``) back to the exact source package version needed by
    ``fetch-debian``.
    """
    pockets = [release, f"{release}-updates", f"{release}-security"]
    render_distro_package_table(_list_distro_packages(DEBIAN_ARCHIVES, pockets, package))


def _matches_kernel_version(pkg: DistroSourcePackage, kernel_version: str) -> bool:
    """Whether a package's source version or any of its kernel ABIs contain ``kernel_version``."""
    return kernel_version in pkg.version or any(kernel_version in abi for abi in pkg.image_abis)


def _search_releases(
    archive_urls: list[str], codenames: list[str], package: str, kernel_version: str
) -> list[tuple[str, DistroSourcePackage]]:
    """Search every given release's pockets for a package version matching ``kernel_version``."""
    results: list[tuple[str, DistroSourcePackage]] = []
    for codename in codenames:
        ui.out_info(f"Checking {codename} ...")
        pockets = [codename, f"{codename}-updates", f"{codename}-security"]
        packages = _list_distro_packages(archive_urls, pockets, package)
        results.extend((codename, pkg) for pkg in packages if _matches_kernel_version(pkg, kernel_version))

    return results


@app.command("search-ubuntu")
def kernel_search_ubuntu(
    kernel_version: Annotated[
        str, typer.Argument(help="Kernel version or ABI substring to search for, e.g. 6.8.0 or 6.8.0-31.")
    ],
    package: Annotated[str, typer.Option("-p", "--package", help="Source package name.")] = "linux",
) -> None:
    """Search every known Ubuntu release for a matching kernel version.

    For when you don't know which release a given kernel build (e.g. from
    ``uname -r``) belongs to -- checks every codename instead of requiring
    ``-r`` up front. Slower than ``list-ubuntu`` (one query per release).
    """
    codenames = _list_ubuntu_codenames()
    render_distro_search_table(_search_releases([UBUNTU_ARCHIVE], codenames, package, kernel_version))


@app.command("search-debian")
def kernel_search_debian(
    kernel_version: Annotated[str, typer.Argument(help="Kernel version or ABI substring to search for, e.g. 3.2.0-4.")],
    package: Annotated[str, typer.Option("-p", "--package", help="Source package name.")] = "linux",
) -> None:
    """Search every known Debian release for a matching kernel version.

    Same idea as ``search-ubuntu``, for Debian. Debian has no equivalent of
    Ubuntu's meta-release listing, so the releases checked are a hardcoded,
    newest-first codename list (``DEBIAN_CODENAMES``).
    """
    render_distro_search_table(_search_releases(DEBIAN_ARCHIVES, DEBIAN_CODENAMES, package, kernel_version))
