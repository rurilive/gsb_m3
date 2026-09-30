"""matchx：朴素二分图匹配工具（改造前基线）。

提供 BipartiteMatcher 类，维护一张二分图（左侧一组点、右侧一组点，
边用对集合表示，重复边只算一次），支持加边、读图、求最大匹配条数与
方案、判定完美匹配、判断给定匹配是否最大，以及枚举导出最小点覆盖与
最大独立集。当前实现一律靠回溯枚举或穷举子集得到答案，规模稍大就
跑不动。

增广路为核心的最大匹配、由最大匹配导出的最小点覆盖与最大独立集、
以及复杂度计数见任务描述。
"""

from .bipartite import (
    BipartiteMatcher,
    InvalidEdgeError,
    MatchError,
    NotMatchedError,
    UnknownNodeError,
)

__all__ = [
    "BipartiteMatcher",
    "MatchError",
    "UnknownNodeError",
    "InvalidEdgeError",
    "NotMatchedError",
]
