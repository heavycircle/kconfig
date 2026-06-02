from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.theme import Theme


KCONFIG_THEME = Theme(
    {
        "debug": "dim italic",
        "info": "bold cyan",
        "warning": "bold yellow",
        "error": "bold red",
        "success": "bold green",
    }
)


class UserInterface:
    """Provide a logging interface."""

    def __init__(self) -> None:
        self.console = Console(theme=KCONFIG_THEME, stderr=True)
        self.debug_mode: bool = False

    def set_debug(self, enabled: bool) -> None:
        """Set the debug mode for the ui.

        Args:
            enabled (bool): True if debug mode is enabled.
        """
        self.debug_mode = enabled
        if enabled:
            self.out_debug("Debug mode enabled!")

    def _print_message(self, tag: str, symbol: str, args: tuple[Any, ...], sep: str) -> None:
        """Helper method to format and print messages.

        Args:
            tag (str): The rich theme tag to use (e.g., "info", "error").
            symbol (str): The symbol to display in brackets (e.g., "*", "!").
            args (tuple[Any, ...]): The arguments to print.
            sep (str): The separator string.

        """
        if tag == "debug" and not self.debug_mode:
            return

        msg = sep.join(str(arg) for arg in args)

        if tag == "debug":
            self.console.print(f"[{tag}][{symbol}] {msg}[/{tag}]")
        else:
            self.console.print(f"[{tag}][{symbol}][/{tag}] {msg}")

    def out_debug(self, *args: Any, sep: str = " ") -> None:
        """Print a debug message.

        Args:
            *args (Any): The arguments to print.
            sep (str): Separator string.

        """
        self._print_message("debug", " ", args, sep)

    def out_info(self, *args: Any, sep: str = " ") -> None:
        """Print an info message with a cyan [*] prefix.

        Args:
            *args (Any): The arguments to print.
            sep (str): Separator string.

        """
        self._print_message("info", "*", args, sep)

    def out_success(self, *args: Any, sep: str = " ") -> None:
        """Print a success message with a green [+] prefix.

        Args:
            *args (Any): The arguments to print.
            sep (str): Separator string.

        """
        self._print_message("success", "+", args, sep)

    def out_warning(self, *args: Any, sep: str = " ") -> None:
        """Print a warning message with a yellow [*] prefix.

        Args:
            *args (Any): The arguments to print.
            sep (str): Separator string.

        """
        self._print_message("warning", "*", args, sep)

    def out_error(self, *args: Any, sep: str = " ") -> None:
        """Print an error message with a red [!] prefix.

        Args:
            *args (Any): The arguments to print.
            sep (str): Separator string.

        """
        self._print_message("error", "!", args, sep)

    @property
    def raw(self) -> Console:
        """Return the console itself."""
        return self.console


ui = UserInterface()
