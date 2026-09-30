"""lichaotree 现状演示。

第一段：在整数定义域上插入若干条直线，逐个横坐标求最小值、最大值
与取到最值的直线标识，再对若干区间求最小值。
第二段：预留的李超线段树演示位子（见文末注释）。
"""

from lichaotree.lines import NaiveLines


def main():
    print("=== 朴素直线集合（现有能力） ===")
    s = NaiveLines([-3, 4])
    specs = [
        (1, 0),       # y = x
        (1, 0),       # y = x（重合，用来演示并列取先）
        (0, 5),       # y = 5
        (-2, 1),      # y = -2x + 1
        (3, -9),      # y = 3x - 9
    ]
    for k, b in specs:
        ident = s.add_line(k, b)
        print("  插入 y = {} x + {} -> 序号 {}".format(k, b, ident))
    print("  定义域           ->", s.domain())
    print("  直线条数         ->", len(s))

    for x in (-3, -1, 0, 2, 4):
        print(
            "  x = {} 最小/最大/取最小者/取最大者 -> {} / {} / {} / {}".format(
                x,
                s.query_min(x),
                s.query_max(x),
                s.query_argmin(x),
                s.query_argmax(x),
            )
        )

    for l, r in ((-3, 4), (0, 4), (2, 2), (-3, -1)):
        print("  区间 [{}, {}) 最小值 -> {}".format(l, r, s.range_min(l, r)))

    lines = s.lines()
    print("  各直线在 x = 0 的取值 ->", [ln.value_at(0) for ln in lines])

    # TODO: 第二段演示（实现后补）
    # 李超线段树改造完成后，在这里补一轮演示：
    # 对同一批直线，用李超线段树求单点最小值与区间最小值，
    # 并让查询顺带给出取到最值的直线标识；
    # 把树上的结果与上面的逐条求值结果并排打印，展示两条路口径逐项一致。


if __name__ == "__main__":
    main()
