"""quotactl 现状演示。

第一段：单层全局配额计数器的 check 与 add。
第二段：预留的迭代演示位子（见文末注释）。
"""

from quotactl.counter import QuotaCounter, QuotaExceeded


def main():
    print("=== 单层全局配额（现有能力） ===")
    c = QuotaCounter(10)
    print("  limit=%d used=%d remaining=%d" % (c.limit, c.used, c.remaining))
    print("  check(4)  =", c.check(4))
    print("  add(4)    =", c.add(4))
    print("  remaining =", c.remaining)
    print("  check(7)  =", c.check(7))
    try:
        c.add(7)
    except QuotaExceeded as exc:
        print("  add(7) 抛出 QuotaExceeded: requested=%d available=%d"
              % (exc.requested, exc.available))
    print("  used 仍为", c.used)

    # TODO(层级配额与两阶段): HierarchicalQuota 实现后，在这里加一段演示：
    # 建一棵父子树，父额度限制子树总和，子节点分配只能在其祖先剩余额度内；
    # 注入假时钟走一遍 reserve 预留、commit 确认消耗与 release 释放，
    # 再演示子节点额度用尽时按策略向兄弟借用、归还后借出方可用量复原，
    # 以及预留超过 ttl 后被时钟回收、回收后可再次预留。


if __name__ == "__main__":
    main()
