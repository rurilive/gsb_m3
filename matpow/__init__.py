"""matpow：纯标准库的线性递推工具包（当前为改造前基线）。

导出 RecurKit、矩阵乘法与矩阵幂的朴素函数，以及全部异常类型。
"""

from .recur import (
    RecurKit,
    RecurErro,
    TermErro,
    MatrixErro,
    mat_mul,
    mat_pow,
)

__all__ = [
    "RecurKit",
    "RecurErro",
    "TermErro",
    "MatrixErro",
    "mat_mul",
    "mat_pow",
]
