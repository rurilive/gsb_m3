"""fixedpt：清算引擎的定点小数库。

Fixed 是定标小数值本身，Domain 是带精度、域宽与策略的操作入口，
ledger 里是累加、计息、分账与对账，rounding 里是低位裁剪。
"""

from fixedpt import ledger
from fixedpt.domain import Domain
from fixedpt.errors import DomainOverflow, FixedPointError, ParseError
from fixedpt.number import Fixed

__all__ = [
    "Domain",
    "DomainOverflow",
    "Fixed",
    "FixedPointError",
    "ParseError",
    "ledger",
]
