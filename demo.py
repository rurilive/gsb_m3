"""persistx 快速演示。

第一段直跑改造前的基线：整份复制式版本留痕，加上区间求和、区间最值与
区间第几小，再切回旧版本确认它一字未改。
第二段预留给改造后的高效路径演示，待实现补齐。
"""

from persistx.pst import PersistSeq


def demo_baseline():
    print("== 基线：整份复制的版本留痕 ==")
    s = PersistSeq([3, 1, 4, 1, 5, 9, 2, 6])
    print("版本0 数据 =", s.values(), " 版本号 =", s.version())

    s.set(1, 100)
    print("改了下标1之后 当前数据 =", s.values(), " 版本号 =", s.version())
    print("版本0 仍然 =", s.values(version=0))

    print("[1,4) 求和 =", s.range_sum(1, 4))
    print("[0,7] 最小 / 最大 =", s.range_min(0, 7), "/", s.range_max(0, 7))
    print("[0,7] 第3小 =", s.kth_smallest(0, 7, 3))

    s.set(4, 0)
    s.set(7, 7)
    print("接连两次修改后 状态 =", s.stats())


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
