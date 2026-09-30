"""朴素并查集现状演示。

第一段：合并、连通判定、集合大小、成员列表与整体回滚的现状能力。
第二段：预留的按大小合并与按时间点回滚演示位子（见文末注释）。
"""

from rbdsu.districts import RollbackDSU


def main():
    print("=== 合并与查询 ===")
    d = RollbackDSU(6, list("abcdef"))
    print(f"  初始集合个数 -> {d.group_count()}")

    d.union("a", "b")
    d.union("c", "d")
    d.union("b", "c")
    print(f"  合并 ab、cd、bc 后 a 与 d 是否连通 -> {d.connected('a', 'd')}")
    print(f"  a 所在集合大小 -> {d.size('a')}")
    print(f"  a 所在集合成员 -> {d.members('a')}")
    print(f"  当前全部集合 -> {d.groups()}")

    print("=== 检查点与回滚 ===")
    start = d.checkout()
    d.union("e", "f")
    print(f"  合并 ef 后集合个数 -> {d.group_count()}")
    d.rollback(start)
    print(f"  回滚到起点后 e 与 f 是否连通 -> {d.connected('e', 'f')}")
    print(f"  回滚后 a 与 d 是否仍连通 -> {d.connected('a', 'd')}")

    # TODO(按大小合并与按时间点回滚): 用成员表整表重算的现状口径，合并与回滚都要
    # 把成员逐个搬来搬去，规模一大就退到平方级。实现后，在这里加一段演示：
    # 改成按大小合并、不做路径压缩，每次合并只改被改写的一侧父指针并把旧父指针
    # 压入历史栈，按栈高回滚到某个时间点；另起一条每次从头重放前若干次合并的
    # 独立做法，在同一批固定输入上对新老两条路径逐项对照连通、大小与集合划分，
    # 并覆盖空森林、单点、重复合并、回滚到起点、回滚到中间、回滚后再合并等边界。


if __name__ == "__main__":
    main()
