"""slotledger: 放号系统里多机房共用的名额同步包。

Ledger 是中心名额账本，管总池、流水与专线状态；Site 是朴素站点，每放一
个名额跑一趟账本；plan 提供确定性事故脚本与纯算术理想值，用来对拍；bench
量吞吐与账本往返。纯标准库，无外部依赖。
"""

from slotledger.bench import candidates, measure, round_trips
from slotledger.buffer import (
    BufferedSite,
    ReconcileAck,
    Reconciler,
    ReconcileMismatch,
    UsageReport,
)
from slotledger.ledger import Entry, Ledger, LinkDown
from slotledger.plan import (
    Ideal,
    PlayoutResult,
    Round,
    Script,
    ideal_admissions,
    make_script,
    playout,
)
from slotledger.site import Site

__all__ = [
    "Entry",
    "Ideal",
    "Ledger",
    "LinkDown",
    "PlayoutResult",
    "Round",
    "BufferedSite",
    "ReconcileAck",
    "Reconciler",
    "ReconcileMismatch",
    "UsageReport",
    "Script",
    "Site",
    "candidates",
    "ideal_admissions",
    "make_script",
    "measure",
    "playout",
    "round_trips",
]
