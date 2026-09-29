"""shardcount 现状演示。

第一段：用单锁全局计数器做几次 incr 与 get，看计数怎么累加、reset
怎么回到零点。
第二段：预留的分片、快照与滑动窗口演示位子（见文末注释）。
"""

from shardcount.counter import ShardCounter


def main():
    print("=== 单锁全局计数器（现有能力） ===")
    c = ShardCounter()
    c.incr()
    c.incr(4)
    c.incr(-1)
    print("  incr 之后 get ->", c.get())
    c.reset()
    print("  reset 之后 get ->", c.get())

    # TODO(分片与滑动窗口): 分片、一致快照、窗口与上限就位后，在这里加一段
    # 演示：新建一个带分片数与注入时钟的计数器，多线程并发地 incr，打印
    # total 是否等于各项之和；推进注入时钟跨过窗口长度，打印 window_count
    # 随窗口外增量淘汰的变化；再演示 incr_by 带上限时要么整体成功、要么
    # 不生效，以及 snapshot 在一次锁内取到的一致值。


if __name__ == "__main__":
    main()
