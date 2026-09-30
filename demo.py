"""chainkit 现状演示。

第一段：一串矩阵维度走一遍现有朴素能力，看最少乘法次数、一个最优括号化、
方案个数、括号串与方案之间的来回。
第二段：预留的递推求值、并列口径、计数递推与括号串互印证的演示位子。
"""

from chainkit import (
    ChainError,
    check_dims,
    naive_plan_cost,
    plan_to_string,
    whole_cost,
    whole_count,
    whole_optimal,
)

CLRS = [30, 35, 15, 5, 10, 20, 25]


def main():
    print("=== 矩阵连乘的最优括号化 ===")
    print("  维度序列:", CLRS)
    print("  矩阵个数:", check_dims(CLRS))

    value, plan = whole_optimal(CLRS)
    text = plan_to_string(CLRS, plan)
    print("  最少乘法次数:", value)
    print("  一个最优括号化:", text)
    print("  从括号串重算乘法次数:", naive_plan_cost(CLRS, text))
    print("  最优方案个数:", whole_count(CLRS))

    three = [10, 20, 30, 40]
    print("  三个矩阵 10x20 20x30 30x40 最少次数:", whole_cost(three))
    print("  左结合 ((01)2) 的代价:", naive_plan_cost(three, "((01)2)"))
    print("  右结合 (0(12)) 的代价:", naive_plan_cost(three, "(0(12))"))

    uniform = [10, 10, 10, 10, 10]
    print("  四个同维矩阵最少次数:", whole_cost(uniform))
    print("  四个同维矩阵最优方案个数:", whole_count(uniform))

    print("  单矩阵链的最少次数:", whole_cost([10, 20]))
    print("  单矩阵链的方案个数:", whole_count([10, 20]))
    print("  零矩阵链的最少次数:", whole_cost([10]))
    print("  零矩阵链的方案个数:", whole_count([10]))

    try:
        naive_plan_cost(three, "(0(3))")
    except ChainError as exc:
        print("  越界下标的诊断:", exc.message, "定位:", exc.position)
    try:
        naive_plan_cost(three, "01")
    except ChainError as exc:
        print("  缺括号的诊断:", exc.message)
    try:
        check_dims([10, 0, 20])
    except ChainError as exc:
        print("  零维度的诊断:", exc.message, "定位:", exc.position)

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
