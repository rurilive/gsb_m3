"""syndigest 现状演示。

第一段：跑一遍全量同步，两边各持一张表，走一次整表发送与整体覆盖；
第二段：预留的摘要驱动反熵演示位子（见文末注释）。
"""

from syndigest import FullSync


def main():
    print("=== 全量同步 ===")
    left = FullSync({"alpha": 1, "beta": 2, "gamma": 3})
    right = FullSync({"delta": 4})
    sent = left.sync_to(right)
    print("  左表键: %s" % (", ".join(left.keys()),))
    print("  发出条目数: %d" % (sent,))
    print("  右表键: %s" % (", ".join(right.keys()),))

    # TODO(摘要与反熵改造): 把 syndigest 从全量同步扩成摘要驱动的反熵同步之后，
    # 在这里补第二段演示：先让两份键空间各自分段求摘要并交换，打印哪些段一致、
    # 哪些段不一致，再对不一致的段深入细分递归定位到具体键；随后开若干个节点，
    # 用固定随机种子反复随机挑对端做反熵，打印每一轮选中了谁以及收敛所需轮数，
    # 最后打印所有节点数据完全一致的结果。摘要分段、差集定位与收敛的口径见
    # README 的目标一节与任务描述。


if __name__ == "__main__":
    main()
