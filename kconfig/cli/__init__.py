from __future__ import annotations

import sys

import typer

from kconfig.utils import KconfigError, ui

from . import config, kernel, structs, symbols


app = typer.Typer(help="Kconfig is a CLI application for reverse-engineering kernel .config configurations.")
app.add_typer(config.app, name="config", help="Inspect kernel configurations.")
app.add_typer(kernel.app, name="kernel", help="Manage local kernel versions.")
app.add_typer(symbols.app, name="symbol", help="Check and verify symbols.")
app.add_typer(structs.app, name="struct", help="Manage and extract structures.")


@app.callback()
def main_config(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging and tracebacks."),
) -> None:
    """Global configurations."""
    ui.set_debug(debug)


def main() -> None:
    """CLI entrypoint."""
    try:
        app()

    except KconfigError as e:
        ui.out_error(e)
        sys.exit(1)

    except Exception as e:  # pylint: disable=broad-exception-caught
        if ui.debug_mode:
            raise

        ui.out_error(e)
        ui.out_error("Run with --debug for more details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
