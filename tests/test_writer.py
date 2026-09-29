"""WriteAll 基线行为的锁定测试。

只覆盖当前实现已经具备的能力：全体写成功、读回最后写入的值、
少数副本不可达时整体写失败。新增行为（法定人数读写、版本、读修复、
部分失败下的可用性）另开测试文件，不改动本文件。
"""

import unittest

from quory import WriteAll
from quory.writer import ReplicaUnavailable


class MemoryReplica:
    """一个确定性的内存副本：set 覆盖写，get 空键返回 None。"""

    def __init__(self, node_id):
        self.node_id = node_id
        self.data = {}
        self.writes = []

    def set(self, key, value):
        self.data[key] = value
        self.writes.append((key, value))

    def get(self, key):
        return self.data.get(key)


class DownReplica(MemoryReplica):
    """一个永远拒绝服务的副本，用来验证全体写的失败路径。"""

    def set(self, key, value):
        raise ReplicaUnavailable("副本 %s 不可达" % (self.node_id,))

    def get(self, key):
        raise ReplicaUnavailable("副本 %s 不可达" % (self.node_id,))


class TestWriteAll(unittest.TestCase):
    def test_put_hits_every_replica(self):
        replicas = [MemoryReplica("a"), MemoryReplica("b"), MemoryReplica("c")]
        writer = WriteAll(replicas)
        writer.put("k", 1)
        for replica in replicas:
            self.assertEqual(replica.get("k"), 1)

    def test_get_returns_written_value(self):
        replicas = [MemoryReplica("a"), MemoryReplica("b"), MemoryReplica("c")]
        writer = WriteAll(replicas)
        writer.put("k", "v")
        self.assertEqual(writer.get("k"), "v")

    def test_get_missing_key_is_none(self):
        replicas = [MemoryReplica("a")]
        writer = WriteAll(replicas)
        self.assertIsNone(writer.get("nope"))

    def test_put_fails_when_any_replica_is_down(self):
        replicas = [MemoryReplica("a"), DownReplica("b"), MemoryReplica("c")]
        writer = WriteAll(replicas)
        with self.assertRaises(ReplicaUnavailable):
            writer.put("k", 1)

    def test_empty_replica_set_is_rejected(self):
        with self.assertRaises(ValueError):
            WriteAll([])

    def test_replica_order_prefers_first_answer(self):
        # 基线读第一个非空回答，不看版本：后面的副本答什么都无所谓。
        first = MemoryReplica("a")
        second = MemoryReplica("b")
        first.set("k", "old")
        second.set("k", "new")
        writer = WriteAll([first, second])
        self.assertEqual(writer.get("k"), "old")


if __name__ == "__main__":
    unittest.main()
