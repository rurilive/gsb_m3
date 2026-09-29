"""idkit 现状演示。

第一段：单机连续生成一批 ID，看单调性与反解结果。
第二段：预留的迭代演示位子（见文末注释）。
"""

from idkit.snowflake import EPOCH_MS, SnowflakeGenerator


def main():
    print("=== 单机连续生成（现有能力） ===")
    g = SnowflakeGenerator(node_id=7)
    base = EPOCH_MS + 10000
    ids = [g.next_id(base) for _ in range(5)]
    for value in ids:
        ts, node, seq = g.parse(value)
        print("  id=%d  ts=%d  node=%d  seq=%d" % (value, ts, node, seq))
    print("  单调递增:", ids == sorted(ids))

    print("=== 跨毫秒 ===")
    ts, node, seq = g.parse(g.next_id(base + 1))
    print("  推进一毫秒后 seq 归零:", seq == 0)

    # TODO(时钟回拨与批量): 回拨等待与拒绝两种模式、序列耗尽自旋、
    # next_batch(n) 段内单调连续与故障原子性、fail-fast 参数校验就位后，
    # 在这里补两段演示：用可回拨的注入时钟展示 wait 模式自愈与 reject 模式抛错，
    # 再展示 next_batch 一批 ID 首尾相接且相邻差为 1。


if __name__ == "__main__":
    main()