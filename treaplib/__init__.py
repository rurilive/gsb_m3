"""treaplib: a tiny standard-library sequence package.

Only the naive array-backed :class:`ListLike` is shipped today. See
:mod:`treaplib.seq` for the current implementation.
"""

from .seq import ListLike

__all__ = ["ListLike"]
