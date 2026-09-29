"""bitrange: a tiny pure-standard-library bitmap toolkit (baseline).

Only the naive flat bitmap is exported today.
"""

from .bits import BitError, FlatBits

__all__ = ["BitError", "FlatBits"]
