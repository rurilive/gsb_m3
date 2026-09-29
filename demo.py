"""hllbox 现状演示。

第一段：用朴素精确集合记几笔，看去重计数、成员查询与并集。
第二段：预留的寄存器草图与误差演示位子（见文末注释）。
"""

from hllbox import ExactSet


def main():
    print("=== 朴素精确去重（现有能力） ===")
    exact = ExactSet()
    for i in range(200):
        exact.add("user-%d" % i)
    for i in range(50):
        exact.add("user-%d" % i)  # 重复加入不改变个数
    print("  不同元素个数 ->", exact.count())
    print("  contains user-7 ->", exact.contains("user-7"))
    print("  contains ghost  ->", exact.contains("ghost"))

    other = ExactSet()
    other.add_many(["user-1000", "user-7"])
    exact.union(other)
    print("  并入另一批之后 ->", exact.count())
    exact.reset()
    print("  reset 之后 ->", exact.count())

    # TODO(寄存器草图与基数估计): 寄存器草图就位后在这里补一段演示：
    # 构造几个桶数不同（如 2 的幂）的草图，对同一批元素逐个 add；
    # 打印二者的估计值，并对照真实不同元素个数，展示估计相对误差
    # 随桶数增大而收窄；再拿两个同参数草图 merge 一次，打印合并后
    # 的并集估计，确认与两边各自加入的结果一致，并打印空草图的估计
    # 为零。桶数越小时误差越大这一点应在打印里直接看得见。


if __name__ == "__main__":
    main()
