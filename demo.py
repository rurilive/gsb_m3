"""gtheor 快速演示。

第一段跑改造前的基线能力（朴素递归判赢输、一步制胜、最少步数、格林数、异或
合并、全体局面）。
第二段预留给改造后的记忆化与拓扑自底向上高效路径演示，待实现补齐。
"""

from gtheor.graph import GameKit


def demo_baseline():
    print("== 基线：朴素递归路径 ==")
    k = GameKit()

    chain = {0: (), 1: (0,), 2: (1,), 3: (2,), 4: (3,)}
    print("长链起点赢输 =", k.outcome(chain, 4))
    print("朴素展开次数 =", k.expansions)

    branch = {0: (), 1: (0,), 2: (1, 0)}
    print("分支起点赢输 =", k.outcome(branch, 2))
    print("一步制胜走法 =", k.winning_move(branch, 2))
    print("最少取胜步数 =", k.min_moves(branch, 2))
    print("起点格林数 =", k.grundy(branch, 2))

    print("全体局面赢输 =", k.all_outcomes(chain))

    heap3 = GameKit().heap_game(3, 3)
    heap1 = GameKit().heap_game(1, 3)
    print("石子堆格林数 =", GameKit().grundy(heap3, 3), GameKit().grundy(heap1, 1))
    print("两堆异或合并胜负 =", k.xor_outcome([(heap3, 3), (heap1, 1)]))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
