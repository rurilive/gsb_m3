"""pseg 现状演示。

第一段：用 FlatCtl 跑一遍点更新、历史版本回看、前缀计数与第 k 小扫描。
第二段：预留的迭代演示位子（见文末注释）。
"""

from pseg import FlatCtl


def main():
    print("=== 朴素可版本化计数（现有能力） ===")
    ctl = FlatCtl(6, 20)
    print(f"  位置数           -> {ctl.size}")
    print(f"  值域上界         -> {ctl.max_value}")
    print(f"  初始计数         -> {ctl.values()}")

    print(f"  更新下标 2 加 5  -> {ctl.add(2, 5)}")
    print(f"  更新下标 4 加 9  -> {ctl.add(4, 9)}")
    v = ctl.snapshot()
    print(f"  存快照           -> 版本 {v} 共 {ctl.version_count()} 个版本")
    ctl.add(2, 3)
    print(f"  再更新下标 2 加 3-> {ctl.values()}")
    print(f"  回看版本 {v} 下标 2 -> {ctl.point(2, v)}")
    print(f"  当前下标 2       -> {ctl.point(2)}")

    print(f"  计数不大于 5 的位置 -> {ctl.count_le(5)}")
    print(f"  首个不小于 4 的下标 -> {ctl.kth_ge(4)}")

    # TODO: 第二段演示（实现后补）
    # 可持久化线段树改造完成后，在这里补一轮演示：
    # 用同一条固定更新序列推进多个版本，回看任意历史版本的下标取值，
    # 演示区间第 k 小与值域区间统计，并把单次更新新建的节点数
    # 与整份数组长度并排打印，让结构共享省下的差距被数字量出来。


if __name__ == "__main__":
    main()
