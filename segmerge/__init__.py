"""segmerge：动态集合合并工具包的朴素基线。

导出 MergeTree 类与全部异常类型。基线把子节点的集合并入父节点时，只会
把一方集合里的元素逐个追加到另一方，自底向上合并整棵树是平方量级；合并
完排一次序，之后所有统计都在这只排序桶上从头扫过，规模一大就慢。
"""

from .dynamic import (
    BadWeightError,
    EmptySetError,
    KOutOfRangeError,
    MergeSegError,
    MergeTree,
    NodeIndexError,
    TreeShapeError,
)

__all__ = [
    "BadWeightError",
    "EmptySetError",
    "KOutOfRangeError",
    "MergeSegError",
    "MergeTree",
    "NodeIndexError",
    "TreeShapeError",
]
