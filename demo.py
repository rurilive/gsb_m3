"""matpow 快速演示。

第一段跑改造前的基线能力（逐项迭代求第n项与前n项和、非齐次递推、朴素矩阵
乘法与逐次相乘的矩阵幂）。
第二段预留给改造后的快速幂路径演示（转移矩阵与二进制拆分），待实现补齐。
"""

from matpow.recur import RecurKit, mat_mul, mat_pow


def demo_baseline():
    print("== 基线：逐项迭代的递推路径 ==")
    k = RecurKit()
    mod = 1000000007

    init = (0, 1)
    coeff = (1, 1)
    print("斐波那契第10项 =", k.nth_term(init, coeff, 10, mod))
    print("迭代步数 =", k.iter_steps)
    print("斐波那契前10项和 =", k.prefix_sum(init, coeff, 10, mod))
    print("非齐次第5项 =", k.nth_term_nonhom(init, coeff, 5, 5, 1000))
    print("迭代步数 =", k.iter_steps)

    print("== 基线：朴素矩阵乘法与逐次相乘的矩阵幂 ==")
    a = [[1, 2], [3, 4]]
    print("矩阵平方 =", mat_mul(a, a, 1000))
    print("矩阵三次方 =", mat_pow(a, 3, 1000))

    print("== 基线：边界行为 ==")
    print("模为一取余 =", k.nth_term(init, coeff, 30, 1))
    print("系数为负取正模 =", k.nth_term((1, 1), (-1, 1), 4, 1000))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
