"""minplus 包：纯标准库的最小加矩阵与递推工具（当前为改造前基线）。

导出朴素工具集 MatPlusKit、独立的最短路与状态转移函数、最小加矩阵乘法与幂，
以及全部异常类型。
"""

from .minplus import (
    INF,
    MatPlusKit,
    MatrixErro,
    MinPlusErro,
    PatternErro,
    mat_mul,
    matrix_power,
    shortest_paths,
    step_transitions,
)

__all__ = [
    "INF",
    "MatPlusKit",
    "MatrixErro",
    "MinPlusErro",
    "PatternErro",
    "mat_mul",
    "matrix_power",
    "shortest_paths",
    "step_transitions",
]
