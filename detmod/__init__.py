"""detmod：模意义下的矩阵运算工具包（当前为改造前基线）。

导出行列式、矩阵乘法、求逆、解方程组、秩与规模计数的朴素函数，以及全部异常类型。
"""

from .matrix import (
    DetErro,
    MatrixErro,
    ModErro,
    InverseErro,
    MatrixKit,
    egcd,
    mod_inverse,
    mat_mul,
    mat_pow,
    det_definitional,
    perm_det,
    inverse_adjugate,
    solve_cramer,
    det_terms,
    perm_count,
    elimination_ops,
    mat_rank,
    row_rank,
    rows_dependent,
)

__all__ = [
    "DetErro",
    "MatrixErro",
    "ModErro",
    "InverseErro",
    "MatrixKit",
    "egcd",
    "mod_inverse",
    "mat_mul",
    "mat_pow",
    "det_definitional",
    "perm_det",
    "inverse_adjugate",
    "solve_cramer",
    "det_terms",
    "perm_count",
    "elimination_ops",
    "mat_rank",
    "row_rank",
    "rows_dependent",
]
