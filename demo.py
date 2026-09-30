"""modarith 现状演示。

第一段：用朴素实现做模幂、模逆元、线性同余方程、组合数与中国剩余定理，
看基线能力。
第二段：预留的迭代演示位子（见文末注释）。
"""

from modarith.modarith import (
    comb_mod,
    crt,
    mod_inverse,
    mod_pow,
    solve_linear_congruence,
)


def main():
    print("=== 朴素模幂（连乘指数次，现有能力） ===")
    print(f"  mod_pow(3, 4, 10)     -> {mod_pow(3, 4, 10)}")
    print(f"  mod_pow(2, 10, 1000)  -> {mod_pow(2, 10, 1000)}")
    print(f"  mod_pow(7, 0, 13)     -> {mod_pow(7, 0, 13)}")

    print("=== 朴素模逆元（逐个试乘） ===")
    print(f"  mod_inverse(3, 7)     -> {mod_inverse(3, 7)}")
    print(f"  mod_inverse(1, 13)    -> {mod_inverse(1, 13)}")

    print("=== 朴素解线性同余方程（枚举候选解） ===")
    print(
        "  solve(3, 1, 7)        -> "
        f"{solve_linear_congruence(3, 1, 7)}"
    )
    print(
        "  solve(4, 2, 6)        -> "
        f"{solve_linear_congruence(4, 2, 6)}"
    )

    print("=== 朴素组合数（先算阶乘再相除） ===")
    print(f"  comb_mod(5, 2, 1000)  -> {comb_mod(5, 2, 1000)}")
    print(f"  comb_mod(10, 1, 1000) -> {comb_mod(10, 1, 1000)}")

    print("=== 朴素中国剩余定理（逐个区间合并） ===")
    print(f"  crt([2, 3], [3, 5])   -> {crt([2, 3], [3, 5])}")
    print(f"  crt([1, 2, 3], [3, 5, 7]) -> {crt([1, 2, 3], [3, 5, 7])}")

    # TODO: 第二段演示（实现后补）
    # 说明：快速幂、扩展欧几里得、阶乘逆元表与中国剩余定理实现后，
    # 在这里补一段演示——同一批输入上，新路径与上面的朴素路径逐项对照，
    # 再展示连乘次数与扩展欧几里得步数相对朴素做法的差距，覆盖指数为零、
    # 模为一、逆元不存在、同余式无解、组合数上标为零或大于下标等边界。


if __name__ == "__main__":
    main()
