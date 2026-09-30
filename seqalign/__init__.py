"""seqalign: 序列比对与编辑距离的朴素求解器。

现状实现全部走枚举：最长公共子序列枚举两个串的全部子序列组合；编辑距离对
每一步枚举删除、插入、替换三种操作再递归；最小编辑方案反复重算同一段前缀。
规模一大就指数甚至更高量级地膨胀，但结果正确、口径固定。
"""

from seqalign.core import (
    EmptyInputError,
    SeqAlign,
    SeqAlignError,
    TypeMismatchError,
)

__all__ = ["EmptyInputError", "SeqAlign", "SeqAlignError", "TypeMismatchError"]
