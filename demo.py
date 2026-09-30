"""crtkit 现状演示。

第一段：用朴素试值实现做同余方程组求解、有无解判定、区间枚举与试值
步数统计，看基线能力在规模变大时的表现。
第二段：预留的迭代演示位子（见文末注释）。
"""

from crtkit.crtkit import (
    count_in_range,
    count_search_steps,
    has_solution,
    search_first_solution,
    smallest_non_negative,
    solutions_in_range,
)


def main():
    print("=== 朴素试值求解（从零逐个往上试，现有能力） ===")
    print(f"  search([2, 3], [3, 5])        -> {search_first_solution([2, 3], [3, 5])}")
    print(f"  search([1, 2, 3], [3, 5, 7])  -> {search_first_solution([1, 2, 3], [3, 5, 7])}")

    print("=== 不互质模数（更大范围硬试） ===")
    print(f"  search([1, 3], [2, 6])        -> {search_first_solution([1, 3], [2, 6])}")

    print("=== 有无解判定（同一个试值过程） ===")
    print(f"  has([2, 3], [3, 5])           -> {has_solution([2, 3], [3, 5])}")
    print(f"  has([0, 1], [2, 4])           -> {has_solution([0, 1], [2, 4])}")

    print("=== 最小非负解与区间枚举 ===")
    print(f"  smallest([2, 3], [3, 5])      -> {smallest_non_negative([2, 3], [3, 5])}")
    print(f"  range([2, 3], [3, 5], 0, 40)  -> {solutions_in_range([2, 3], [3, 5], 0, 40)}")
    print(f"  count([2, 3], [3, 5], 0, 40)  -> {count_in_range([2, 3], [3, 5], 0, 40)}")

    print("=== 试值次数（规模一大就爆） ===")
    print(f"  steps([2, 3], [3, 5])                  -> {count_search_steps([2, 3], [3, 5])}")
    print(
        "  steps([2, 3], [1000003, 1000033])      -> "
        f"{count_search_steps([2, 3], [1000003, 1000033])}"
    )

    # TODO: 第二段演示（实现后补）
    # 说明：互质模数的中国剩余定理与不互质的扩展合并实现后，在这里补一段
    # 演示——同一批方程上，新路径给出的最小非负解、解模数、区间内解个数与
    # 具体解，逐项与上面的朴素路径对照，再拿另一条先合并成单个模数与余数
    # 再枚举的做法互相印证，并把朴素试值次数与合并次数摆在一起看规模差距，
    # 覆盖单个方程、模数为一、模数互质、模数不互质、含冲突无解、余数为负、
    # 余数大于模数、大模数、系数为零方程等边界。


if __name__ == "__main__":
    main()
