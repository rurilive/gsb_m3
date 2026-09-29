"""matchx 包：纯标准库的字符串检索工具。"""

from .search import (
    MatchError,
    InvalidPatternError,
    NaiveSearch,
    find,
    find_all,
    has,
    count,
)

__all__ = [
    "MatchError",
    "InvalidPatternError",
    "NaiveSearch",
    "find",
    "find_all",
    "has",
    "count",
]
