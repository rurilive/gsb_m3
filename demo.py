"""beatsx 快速演示。

第一段直跑改造前的基线：区间取最小值逐元素压低，再叠加区间加、区间赋值
与区间求和、区间最值，最后看一眼操作计数与访问量统计。
第二段预留给改造后的高效路径演示，待实现补齐。
"""

from beatsx.segment import BeatsSeq


def demo_baseline():
    print("== 基线：逐元素改写与逐元素重扫 ==")
    s = BeatsSeq([5, 3, 8, 1, 9, 2])
    print("初始数据 =", s.values())

    dropped = s.range_chmin(0, 4, 4)
    print("对 [0,4) 取上界 4，落下总和 =", dropped, " 数据 =", s.values())

    s.range_add(1, 5, 10)
    print("对 [1,5) 加 10，数据 =", s.values())

    s.range_assign(0, 2, 0)
    print("对 [0,2) 赋值 0，数据 =", s.values())

    print("[0,6) 求和 =", s.range_sum(0, 6))
    print("[0,6) 最小 / 最大 =", s.range_qmin(0, 6), "/", s.range_qmax(0, 6))
    print("操作次数 =", s.op_count(), " 访问量统计 =", s.touched())


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
