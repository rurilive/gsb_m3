"""konig：朴素二分图工具（改造前基线）。

提供 NaiveGraph 类，维护一张二分图（左侧一组点、右侧一组点，
边用有序对登记），支持加边、用增广路深搜求最大匹配，以及用
左侧点子集枚举求点覆盖。两项能力都只走最直白的循环与枚举，
规模一大就指数级变慢，且点覆盖只从左点里挑，范围被限死。
"""

from .graph import (
    DuplicateEdgeError,
    IllegalPointError,
    KonigError,
    NaiveGraph,
    NotMatchedError,
    SelfLoopError,
    UnknownPointError,
)

__all__ = [
    "DuplicateEdgeError",
    "IllegalPointError",
    "KonigError",
    "NaiveGraph",
    "NotMatchedError",
    "SelfLoopError",
    "UnknownPointError",
]
