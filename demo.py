"""pathcount 现状演示。

第一段：在一张小的有向图上跑基线能力，看定长走法数、两点路径数、上界内的
走法数、回路判定、以及朴素矩阵乘法与逐次相乘的矩阵幂。
第二段：预留给改造后的快速路径演示（邻接矩阵快速幂、增广矩阵前缀和、两种
做法的逐项对照），见文末注释，待实现补齐。
"""

from pathcount.count import DirectedGraph, PathCounter


def demo_baseline():
    print("== 基线：有向图 ==")
    g = DirectedGraph(nodes=[0, 1, 2, 3],
                      edges=[(0, 1), (0, 2), (1, 3), (2, 3)])
    print("节点 =", g.nodes())
    print("边   =", g.edges())
    print("邻接矩阵 =", g.adjacency_matrix())

    c = PathCounter(g)
    print("== 基线：定长走法数（逐层深度搜索枚举） ==")
    print("走两步从零到三 =", c.count_walks_exact(0, 3, 2))
    print("深度搜索访问次数 =", c.depth_steps)
    print("枚举走法条数     =", c.enum_paths)
    print("走一步从零到三 =", c.count_walks_exact(0, 3, 1))
    print("零步从零到零   =", c.count_walks_exact(0, 0, 0))

    print("== 基线：两点之间全部路径数（枚举简单路径） ==")
    print("零到三全部路径 =", c.count_paths_between(0, 3))

    print("== 基线：长度不超过上界的走法数 ==")
    print("零到三不超过三步 =", c.count_walks_up_to(0, 3, 3))

    print("== 基线：回路判定与最短回路 ==")
    cyc = DirectedGraph(nodes=[0, 1, 2],
                        edges=[(0, 1), (1, 2), (2, 0)])
    cc = PathCounter(cyc)
    print("长度三回路存在 =", cc.has_cycle_of_length(3))
    print("最短回路长度   =", cc.shortest_cycle())

    print("== 基线：朴素矩阵乘法与逐次相乘的矩阵幂 ==")
    a = g.adjacency_matrix()
    print("矩阵一次方 =", c.mat_pow(a, 1, 1000))
    print("矩阵二次方 =", c.mat_pow(a, 2, 1000))
    print("矩阵乘法次数 =", c.mult_count)


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
