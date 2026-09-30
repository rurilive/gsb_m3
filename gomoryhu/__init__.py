"""gomoryhu: 无向图全体点对最小割的改造前基线工具。

当前只有一条朴素路：对每一对点各自单独跑一遍最大流求这一对的最小割，
任意两点都从头再算一遍，规模一大就按点对数量乘以一次最大流的时间上涨。
见 gomoryhu.core。用戈莫里胡树把全体点对最小割一次压出来的做法见任务描述。
"""

from .core import (
    Erro,
    GomoryHu,
    GomoryHuError,
    GraphError,
    UnknownNodeError,
)

__all__ = [
    "GomoryHu",
    "Erro",
    "GraphError",
    "GomoryHuError",
    "UnknownNodeError",
]
