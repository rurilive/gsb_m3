"""bipmatch: 二分图匹配工具包（纯标准库）。

现有实现只有一个朴素匹配器：对每个左侧顶点用增广路暴力搜索，
反复整题重搜，只报匹配边数与边集，不提供最小顶点覆盖，
也不做匹配是否最大的判定，更不记录搜索规模。
"""

from .matcher import (
    BipMatchError,
    CannotMatchError,
    DuplicateEdgeError,
    NaiveMatcher,
    SelfLoopError,
)

__all__ = [
    "BipMatchError",
    "CannotMatchError",
    "DuplicateEdgeError",
    "NaiveMatcher",
    "SelfLoopError",
]
