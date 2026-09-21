"""changelogd: 按版本号记录字段变更的日志。"""

from .changelog import DELETED, Change, ChangeLog
from .merge import (
    Candidate,
    Conflict,
    MergeResult,
    MergedChange,
    first_write_wins,
    last_write_wins,
    merge,
)

__all__ = [
    "DELETED",
    "Candidate",
    "Change",
    "ChangeLog",
    "Conflict",
    "MergeResult",
    "MergedChange",
    "first_write_wins",
    "last_write_wins",
    "merge",
]
