from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class KconfigError(Exception):
    """Base exception class for all Kconfig CLI operations."""


# --- File System Errors ---------------------------------------


class KconfigFileError(KconfigError):
    """Base class for file system and I/O errors."""


class KconfigFileInvalidError(KconfigFileError):
    """Raised when a file exists but is malformed or unreadable."""

    def __init__(self, path: Path | str, reason: str) -> None:
        super().__init__(f"Invalid file '{path}': {reason}")


# --- Query Errors ---------------------------------------------


class KconfigQueryError(KconfigError):
    """Base class for Tree-sitter query execution errors."""


class KconfigQuerySyntaxError(KconfigQueryError):
    """Raised when a Tree-sitter .scm query file is malformed."""

    def __init__(self, query_name: str, syntax_error: str) -> None:
        super().__init__(f"Syntax error in query '{query_name}': {syntax_error}")


class KconfigASTAnomalyError(KconfigQueryError):
    """Raised when the AST structure violates C syntax assumptions (e.g., missing bodies)."""

    def __init__(self, node_type: str, details: str) -> None:
        super().__init__(f"AST anomaly detected in '{node_type}': {details}")


# --- Symbol Resolution Errors ---------------------------------


class KconfigSymbolError(KconfigError):
    """Base class for symbol lookup and resolution events."""


class KconfigSymbolNotFoundError(KconfigSymbolError):
    """Raised when a target symbol cannot be found in the provided codebase."""

    def __init__(self, target_name: str, search_root: Path | str) -> None:
        self.target_name = target_name
        super().__init__(f"Cannot find definition for '{target_name}' in '{search_root}'")


class KconfigSymbolAliasedError(KconfigSymbolError):
    """Raised when a target struct is actually a macro alias or typedef."""

    def __init__(self, original_name: str, true_name: str) -> None:
        self.original_name = original_name
        self.true_name = true_name
        super().__init__(f"Symbol '{original_name}' is an alias for '{true_name}'")


# --- Analysis Errors ------------------------------------------


class KconfigToolingError(KconfigError):
    """Base class for external tooling or host environment failures."""


class KconfigSubprocessFailedError(KconfigToolingError):
    """Raised when an external tool (pahole, genksyms) returns a non-zero exit code."""

    def __init__(self, tool_name: str, stderr: str) -> None:
        super().__init__(f"Tool '{tool_name}' failed to execute:\n{stderr}")


class KconfigAnalysisError(KconfigError):
    """Base class for layout diffing and validation errors."""


class KconfigLayoutMismatchError(KconfigAnalysisError):
    """Raised when compiled memory layout conflicts with source Kconfig guards."""

    def __init__(self, struct_name: str, mismatch_details: str) -> None:
        super().__init__(f"Analysis failed for '{struct_name}': {mismatch_details}")
