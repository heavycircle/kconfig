from __future__ import annotations


class KconfigError(Exception):
    """Base exception class."""


class KconfigQueryError(KconfigError):
    """Errors where query results do not return expected results.

    This may be a problem with the query or the code beign queried.
    """
