from __future__ import annotations


class KconfigError(Exception):
    """Base exception class."""


class KconfigFileError(KconfigError):
    """Errors relating to the file system."""


class KconfigFileInvalidError(KconfigFileError):
    """Errors pertaining to invalid files."""


class KconfigFileNoMatchError(KconfigFileError):
    """Errors where a matching file cannot be found."""


class KconfigQueryError(KconfigError):
    """Base class for Query errors."""


class KconfigQueryInvalidError(KconfigQueryError):
    """Errors relating to invalid structured queries."""


class KconfigQueryNoMatchError(KconfigQueryError):
    """Errors relating to valid queries finding no matches."""


class KconfigQueryImpossibleError(KconfigQueryError):
    """Errors relating to impossible edge cases for queries."""


class KconfigAnalysisError(KconfigError):
    """Base class for Analysis errors."""


class KconfigAnalysisInvalidError(KconfigAnalysisError):
    """Errors relating to invalid analysis issues."""
