# Kconfig

_Kconfig_ aims to reverse-engineer kernel `.config` files using existing kernel artifacts.

## Background

Reversing a `.config` from a kernel is a extremely difficult task. This is particularly challenging when a kernel is configured with [modversions](https://www.kernel.org/doc/html/latest/kbuild/modules.html#module-versioning) (`CONFIG_MODVERSIONS=y`), which requires kernel modules to be built with proper signatures (CRC checksums) for all function signatures and declared structures. You can check if a kernel was built with `modversions` by inspecting `/boot/config-$(uname -r)`, and local kernel modules will reveal their versioning requirement when inspected with `modinfo`.

_Kconfig_ takes away the grunt work of reverse engineering this configuration. It automatically checks structures from known-good modules, then utilizes the specific kernel's header files to determine the exact `CONFIG` values required to produce a matching kernel.

## Limitations and Roadmap

Kernel environments are highly variable. Currently, _Kconfig_ focuses on standard mainline kernels and does not yet support:

- **"Frankenstein" Kernels**: Kernels that backport newer kernel versions onto older ones to remove bugs without refactoring major API changes. _Kconfig_ cannot yet identify or report on these hybrid environments.
- **Heavily Patched Kernels**: Common security or feature patches (such as the _PREEMPT\_RT_ or _linux-pf_ patches) provide additional security, watchdog metrics, and minification. _Kconfig_ does not currently identify these specific patch sets.

_Kconfig_ **does** report when structure configurations are impossible to achieve by solely modifying `CONFIG` values. This can hopefully lead end-users to recognize patched kernels.

## Requirements

System Requirements:

- **OS**: Linux (Currently untested on macOS/Windows)
- **Python**: 3.10+

Software Requirements:

- **uv**: Required for fast, deterministic dependency management ([Install uv](https://docs.astral.sh/uv/))
- **pahole**: _Kconfig_ heavily relies on `pahole` for underlying structural operations. You can install it via your system's package manager:
    - **Ubuntu**/**Debian**: `sudo apt install pahole`
    - **Fedora**/**RHEL**: `sudo dnf install pahole`
    - **Arch Linux**: `sudo pacman -S pahole`

## Installation

Currently, _Kconfig_ is run directly from source.

1. Clone the repository:

    ```bash
    git clone https://github.com/heavycircle/kconfig.git
    cd kconfig
    ```

2. Sync the dependencies to match the `uv.lock` file:

    ```bash
    uv sync
    ```

## Running Kconfig

_Kconfig_ provides a robust command-line interface. You can execute the CLI safely within its isolated environment using `uv run`.

To see all available commands, options, and flags, check the help menu:

```bash
uv run kconfig --help
```

Example Usage: Analyzing CONFIG options for `struct file` on Linux 5.15.1 (Ubuntu 22.04) against known modules:

```bash
uv run kconfig struct compare -k 5.15.1 -m modules file
```

## Contributing and Feedback

This project is actively seeking users and feedbacks! Different kernel versions boast their own set of problems for parsing source code and modules. If you run into issues, have feature requests, or want to contribute code, please open an issue or submit a Pull Request. Code formatting and linting standards are defined in `pyproject.toml` and can be run via `uv run ruff format` and `uv run ruff check`.
