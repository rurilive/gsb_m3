"""tspx 现状演示。

第一段：朴素枚举——把全部排列走一遍挑最短回路，再对每个起点各做一次最近邻。
第二段：预留的精确与近似路径优化演示位子（见文末注释）。
"""

from tspx import TspSolver


SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def main():
    print("=== 朴素枚举：四点正方形 ===")
    solver = TspSolver(SQUARE)
    length, order = solver.enumerate_best()
    print(f"  枚举全部 {solver.enumerate_count()} 个排列")
    print(f"  最短回路 -> {length:.4f}，次序 {order}")
    nn_len, nn_order, nn_start = solver.nearest_neighbor_over_starts()
    print(f"  逐起点最近邻 -> {nn_len:.4f}，次序 {nn_order}，起点 {nn_start}")
    print(f"  朴素最近邻与枚举口径差 -> {nn_len - length:.4f}")

    print("=== 朴素暴力：五点 ===")
    five = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (1.0, 1.0)]
    solver5 = TspSolver(five)
    length5, order5 = solver5.enumerate_best()
    print(f"  枚举 {solver5.enumerate_count()} 个排列 -> {length5:.4f}，次序 {order5}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
