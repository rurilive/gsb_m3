"""minplus 现状演示。

第一段：跑改造前的基线能力（固定步数最短路、定步数状态转移、最小加矩阵幂）。
第二段：预留的快速路径演示位子（见文末注释）。
"""

import math

from minplus.minplus import MatPlusKit, shortest_paths, step_transitions


def demo_baseline():
    print("== 基线：固定步数最短路（重复松弛） ==")
    nodes = ["s", "a", "b", "t"]
    edges = [("s", "a", 2.0), ("a", "b", 3.0), ("s", "b", 10.0),
             ("b", "a", 0.0), ("b", "t", 1.0)]
    for steps in (0, 1, 2, 3):
        matrix, order = shortest_paths(nodes, edges, steps)
        row_s = ["inf" if math.isinf(x) else x for x in matrix[0]]
        print(f"  走 {steps} 步：从 s 出发到 {order} 的距离 = {row_s}")

    print("== 基线：定步数状态转移（逐步枚举） ==")
    kit = MatPlusKit()
    init = [0.0, math.inf, math.inf, math.inf]
    for steps in (1, 2, 4):
        vec, _ = step_transitions(init, nodes, edges, steps)
        shown = ["inf" if math.isinf(x) else x for x in vec]
        print(f"  转移 {steps} 步：{shown}")

    print("== 基线：最小加矩阵幂与计数 ==")
    base = [[0.0, 1.0, math.inf], [math.inf, 0.0, 2.0], [4.0, math.inf, 0.0]]
    power = kit.matrix_power(base, 8)
    print(f"  八次幂 = {power}")
    print(f"  朴素乘法次数 = {kit.mult_count}")
    kit.shortest_paths(nodes, edges, 6)
    print(f"  六步最短路整表松弛遍数 = {kit.iter_steps}")


def demo_fast():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_fast()


if __name__ == "__main__":
    main()
