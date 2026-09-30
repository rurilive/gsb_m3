"""gomoryhu 现状演示。

第一段：逐对点各自单独跑一遍最大流求最小割，打印若干图上的点对最小割、
割侧点集以及本次求解的增广次数；
第二段：预留的戈莫里胡树构造与独立对照演示位子（见文末注释）。
"""

from gomoryhu import GomoryHu, Erro


def main():
    print("=== 逐对点最大流（朴素现状） ===")
    # 一条链：0 连 1 容量五，1 连 2 容量九，2 连 3 容量三。
    chain = [(0, 1, 5), (1, 2, 9), (2, 3, 3)]
    graph = GomoryHu(chain)
    print("  结点 %s" % graph.nodes())

    pair = graph.pair_cut(0, 3)
    print("  零号到三号的最小割容量 %d" % pair["value"])
    print("  割侧点集 %s" % pair["side"])
    print("  这一次求解的增广次数 %d" % pair["augmentations"])

    print("  全部点对最小割 %s" % graph.all_pairs_cuts())

    print("  零号到三号是否被二号隔开 %s" % graph.pair_disjoint(0, 3, 2))
    print("  零号到一号是否被三号隔开 %s" % graph.pair_disjoint(0, 1, 3))

    graph.reset_augment_count()
    graph.all_pairs_cuts()
    print("  逐对点求解累计增广次数 %d" % graph.augment_count())

    try:
        graph.pair_cut(0, 9)
    except Erro as err:
        print("  越界结点被统一基类拦下 %s" % type(err).__name__)

    # TODO: 第二段演示（实现后补）
    #
    # 在 gomoryhu 里补出戈莫里胡树的构造之后，在这里加一段演示：对同一批
    # 无向图，用逐对点跑最大流的朴素路求出全体点对最小割，再用戈莫里胡树
    # 构造所求的全体点对最小割，两条路逐项对照打印是否一致；并排打印
    # 朴素路跑的最大流次数与树构造跑的最大流次数，覆盖两点图、链、星形、
    # 平行边、完全图、单点图这些边界，确认树构造只需点数减一次最大流就能
    # 得到全体点对最小割。


if __name__ == "__main__":
    main()
