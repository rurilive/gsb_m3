"""walog 现状演示。

第一段：往内存列表追加负载、按位置读回、长度与校验。
第二段：预留的检查点与崩溃恢复演示位子（见文末注释）。
"""

from walog import InvalidLsn, Log


def main():
    print("=== 追加与读取 ===")
    log = Log()
    log.append({"op": "put", "key": "a", "value": 1})
    log.append({"op": "put", "key": "b", "value": 2})
    log.append({"op": "delete", "key": "a"})
    print("  条目数:", len(log))
    print("  位置 0 的负载:", log.read(0))
    print("  位置 2 的负载:", log.read(2))

    print("=== 校验与清空 ===")
    try:
        log.read(5)
    except InvalidLsn as exc:
        print("  越界位置被拒:", exc)
    log.reset()
    print("  清空后条目数:", len(log))

    # TODO(检查点与崩溃恢复): 带序号的条目、检查点、截断与重放、崩溃恢复与
    # 校验和都补齐后，在这里加一段演示：
    # 每条 put 与 delete 落一条带序号与校验和的日志，append 返回该序号；
    # 打一个检查点记下当前状态快照与已刷序号，再往后写几条；
    # 模拟在某处崩溃截断，从最近检查点加其后日志重建状态机；
    # 打印恢复出的状态与崩溃前的状态逐项一致；
    # 再演示一条校验和损坏的条目在重放时被检出、停在最后一条完好条目.


if __name__ == "__main__":
    main()
