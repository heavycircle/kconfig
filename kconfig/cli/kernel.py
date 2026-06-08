from __future__ import annotations

import tarfile
from typing import Annotated

import requests
import typer
from rich.progress import BarColumn, DownloadColumn, Progress, SpinnerColumn, TextColumn, TransferSpeedColumn

from kconfig.styling_api import render_kernel_version_table, ui
from kconfig.utils import CACHE_DIR


app = typer.Typer()


@app.command("list")
def kernel_list() -> None:
    """List the available cached kernels."""
    kernel_dir = CACHE_DIR / "kernel"
    versions = [p.name.replace("linux-", "") for p in kernel_dir.glob("linux-*") if p.is_dir()]

    def version_sort(v: str) -> list[int]:
        try:
            return [int(p) for p in v.split(".")]
        except ValueError:
            return [0]

    render_kernel_version_table(sorted(versions, key=version_sort, reverse=True), kernel_dir)


@app.command("fetch")
def kernel_fetch(
    version: Annotated[str, typer.Argument(help="Linux kernel version to fetch.")],
) -> None:
    """Fetch a kernel from Linux."""
    ui.out_info(f"Fetching Kernel: {version}")

    major = version.split(".", maxsplit=1)[0]
    url = f"https://cdn.kernel.org/pub/linux/kernel/v{major}.x/linux-{version}.tar.xz"

    kernel_dir = CACHE_DIR / "kernel"
    kernel_dir.mkdir(parents=True, exist_ok=True)

    tarball_path = kernel_dir / f"linux-{version}.tar.xz"
    extract_dir = kernel_dir / f"linux-{version}"
    if extract_dir.exists():
        ui.out_info(f"Kernel {version} is already cached at {extract_dir}")
        return

    try:
        # Get the file from the URL.
        with requests.get(url, stream=True, timeout=(10, 60)) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))

            with (
                tarball_path.open("wb") as f,
                Progress(
                    SpinnerColumn(),
                    TextColumn("[bold cyan]Downloading..."),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    transient=True,
                ) as progress,
            ):
                task = progress.add_task("download", total=total_size)
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))

        ui.out_info("Extracting tarball...")
        with tarfile.open(tarball_path, "r:xz") as tar:
            tar.extractall(path=kernel_dir)

        tarball_path.unlink()
        ui.out_success(f"Kernel {version} ready at {extract_dir}")
    except requests.exceptions.ReadTimeout as e:
        ui.out_error("Download timed out. The kernel.org mirror was too slow.")
        if tarball_path.exists():
            tarball_path.unlink()
        raise typer.Exit(1) from e

    except requests.exceptions.HTTPError as e:
        if r.status_code == 404:
            ui.out_error(f"Version {version} not found.")
        else:
            ui.out_error(f"Failed to download: {e}")
        raise typer.Exit(1) from e
