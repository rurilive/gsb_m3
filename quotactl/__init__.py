"""quotactl：配额发放工具，纯标准库。"""

from .counter import QuotaCounter, QuotaError, QuotaExceeded

__all__ = [
    "QuotaCounter",
    "QuotaError",
    "QuotaExceeded",
]
