"""quory 现状演示。

第一段：三个内存副本，走一次全体写与读回，看基线行为。
第二段：留给法定人数改造后的演示位子（见文末注释）。
"""

from quory import WriteAll


class MemoryReplica:
    """确定性的内存副本。"""

    def __init__(self, node_id):
        self.node_id = node_id
        self.data = {}

    def set(self, key, value):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)


def main():
    print("=== 全体写入（现有能力） ===")
    replicas = [MemoryReplica("n1"), MemoryReplica("n2"), MemoryReplica("n3")]
    writer = WriteAll(replicas)
    writer.put("k", 1)
    print("  写入 k=1 到全部副本")
    print("  各副本读数 ->", [r.get("k") for r in replicas])
    print("  writer.get(k) ->", writer.get("k"))

    # TODO(法定人数改造): 法定人数读写、版本与时间戳、读修复、部分失败演示到位后，
    # 在这里加一段：用多数确认的写法写一个新值，只让多数副本可达，看写能否成功；
    # 让一个副本先落后，再触发一次读修复，看落后副本的版本追平到最新；
    # 最后恢复所有副本，跑一次一致性检查，确认已确认写没有被旧值覆盖。


if __name__ == "__main__":
    main()
