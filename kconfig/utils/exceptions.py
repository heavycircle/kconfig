from __future__ import annotations


class KconfigError(Exception):
    """Base exception class."""


class KconfigQueryError(KconfigError):
    """Base class for Query errors."""


class KconfigFileError(KconfigError):
    """Errors relating to the file system."""


class KconfigQueryInvalidError(KconfigQueryError):
    """Errors relating to invalid structured queries."""


class KconfigQueryNoMatchError(KconfigQueryError):
    """Errors relating to valid queries finding no matches."""


class KconfigQueryImpossibleError(KconfigQueryError):
    """Errors relating to impossible edge cases for queries."""
