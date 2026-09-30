"""detmod 快速演示。

第一段跑改造前的基线能力（按定义展开与全排列枚举求行列式、三重循环矩阵乘法、
伴随矩阵求逆、克拉默法则解方程组、全排列项数与高斯消元操作次数的规模对照、
模意义下求秩与行向量线性相关判定）。
第二段预留给改造后的快速路径演示（高斯消元求行列式与求逆、分块乘法与快速幂、
消元回代解方程组），待实现补齐。
"""

from detmod.matrix import (
    DetErro,
    MatrixErro,
    ModErro,
    InverseErro,
    MatrixKit,
    perm_det,
    det_definitional,
    inverse_adjugate,
    solve_cramer,
    mat_mul,
    mat_pow,
    det_terms,
    elimination_ops,
    mat_rank,
    rows_dependent,
)


def demo_baseline():
    print("== 基线：行列式的两条朴素路径 ==")
    mod = 1000000007
    a = [[1, 2, 3], [4, 5, 6], [7, 8, 10]]
    print("按定义递归展开的行列式 =", det_definitional(a, mod))
    print("全排列枚举的行列式 =", perm_det(a, mod))

    print("== 基线：矩阵乘法与逐次相乘的矩阵幂 ==")
    x = [[1, 2], [3, 4]]
    print("矩阵平方 =", mat_mul(x, x, 1000))
    print("矩阵三次方 =", mat_pow(x, 3, 1000))

    print("== 基线：伴随矩阵求逆与克拉默法则解方程组 ==")
    b = [[2, 0, 1], [1, 3, 2], [1, 1, 2]]
    print("逆矩阵 =", inverse_adjugate(b, 97))
    coeff = [[2, 1], [1, 3]]
    rhs = [5, 10]
    print("方程组唯一解 =", solve_cramer(coeff, rhs, 97))
    print("是否可逆 =", MatrixKit().is_invertible(b, 97))

    print("== 基线：规模对照 ==")
    n = 6
    print("全排列展开项数 =", det_terms(n))
    print("高斯消元操作次数 =", elimination_ops(n))

    print("== 基线：模意义下求秩与线性相关判定 ==")
    print("矩阵的秩 =", mat_rank([[1, 2, 3], [4, 5, 6], [7, 8, 9]], 97))
    print("行向量是否相关 =", rows_dependent([[1, 2], [2, 4]], 97))

    print("== 基线：边界行为 ==")
    print("零矩阵行列式 =", det_definitional([[0, 0], [0, 0]], 97))
    print("单位阵行列式 =", det_definitional([[1, 0], [0, 1]], 97))
    print("一阶行列式 =", det_definitional([[5]], 97))
    print("行列式为零不可逆 =", MatrixKit().is_invertible([[1, 2], [2, 4]], 97))
    print("模为一取余 =", det_definitional(a, 1))
    try:
        inverse_adjugate([[1, 2], [2, 4]], 97)
    except InverseErro as err:
        print("奇异矩阵求逆被拒 =", err)
    try:
        det_definitional([[1, 2, 3], [4, 5, 6]], 97)
    except MatrixErro as err:
        print("非方阵求行列式被拒 =", err)


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
