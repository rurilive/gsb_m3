"""entropack: a small pure-stdlib entropy coding library.

The public surface currently exports only the baseline fixed-width encoder.
"""

from .codec import EntropyError, FixedWidth

__all__ = ["EntropyError", "FixedWidth"]
