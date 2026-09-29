"""raftlite 现状演示。

第一段：追加日志、读任期、末尾截断与索引校验。
第二段：预留的多节点复制与多数提交演示位子（见文末注释）。
"""

from raftlite import InvalidIndex, Log


def main():
    print("=== 追加日志 ===")
    log = Log()
    log.append(term=1, command={"op": "set", "key": "a", "value": 1})
    log.append(term=1, command={"op": "set", "key": "b", "value": 2})
    log.append(term=2, command={"op": "del", "key": "a"})
    print("  日志长度:", log.size())
    print("  最后索引:", log.last_index())
    print("  最后任期:", log.last_term())
    print("  索引 2 的任期:", log.term_at(2))

    print("=== 截断与校验 ===")
    dropped = log.truncate_from(3)
    print("  丢掉条数:", len(dropped))
    print("  截断后长度:", log.size())
    print("  截断后最后任期:", log.last_term())
    try:
        log.term_at(5)
    except InvalidIndex as exc:
        print("  越界索引被拒:", exc)
    log.reset()
    print("  重置后长度:", log.size())

    # TODO(多节点复制与一致性): 节点、领导复制、多数提交与应用、任期与选举、
    # 冲突回退与覆盖都补齐后，在这里加一段演示：
    # 建一组内存节点并选出一个领导，领导追加几条命令后复制到跟随者；
    # 打印多数确认后提交并应用到状态机的顺序；
    # 打印未获多数确认的条目仍停在未提交、没有被应用；
    # 打印日志落后的跟随者回退冲突后与领导补齐.


if __name__ == "__main__":
    main()