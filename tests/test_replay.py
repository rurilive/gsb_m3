"""分组死信、定向重放与归档的测试。

时钟全部外部注入，精确断言归档时刻、分组与触发先后。
"""

import unittest

from deadletter.queue import DeadLetterQueue


class DecodeError(Exception):
    """模拟反序列化炸。"""


class TimeoutError(Exception):
    """模拟超时炸。"""


class ManualClock:
    """可手动推进的注入时钟。"""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, delta):
        self.now += delta


class RoutingConsumer:
    """按 id 路由异常类型的消费者；broken 可随时改动模拟修复。"""

    def __init__(self, broken):
        # broken: {id: 异常类型}，键存在即失败
        self.broken = dict(broken)
        self.seen = []

    def __call__(self, msg):
        mid = msg["id"]
        self.seen.append(mid)
        if mid in self.broken:
            exc_type = self.broken[mid]
            raise exc_type("boom %s" % mid)


def msg(mid, payload=None):
    return {"id": mid, "payload": payload if payload is not None else mid}


def sink(q, mid, exc_type, payload=None):
    """让一条消息失败到上限、沉进对应分组。"""
    q._handler.broken[mid] = exc_type
    for _ in range(q._max_retries):
        q.consume(msg(mid, payload))


class TestGrouping(unittest.TestCase):
    def test_dead_split_by_failure_reason(self):
        clock = ManualClock(100.0)
        consumer = RoutingConsumer({})
        q = DeadLetterQueue(consumer, max_retries=1, clock=clock)
        sink(q, "d1", DecodeError)
        sink(q, "t1", TimeoutError)
        sink(q, "d2", DecodeError)

        groups = q.dead_groups()
        self.assertEqual(set(groups), {"DecodeError", "TimeoutError"})
        self.assertEqual([r["msg"]["id"] for r in groups["DecodeError"]],
                         ["d1", "d2"])
        self.assertEqual([r["msg"]["id"] for r in groups["TimeoutError"]],
                         ["t1"])

    def test_group_record_carries_payload_and_failure_context(self):
        clock = ManualClock(5.0)
        q = DeadLetterQueue(RoutingConsumer({}), max_retries=2, clock=clock)
        sink(q, "d1", DecodeError, payload={"raw": "???"})

        rec = q.dead_groups()["DecodeError"][0]
        self.assertEqual(rec["attempts"], 2)
        self.assertEqual(rec["msg"]["payload"], {"raw": "???"})
        self.assertEqual(rec["error"], "boom d1")
        self.assertEqual(rec["dead_at"], 5.0)

    def test_groups_are_independent_snapshots(self):
        q = DeadLetterQueue(RoutingConsumer({}), max_retries=1)
        sink(q, "d1", DecodeError)
        groups = q.dead_groups()
        groups["DecodeError"][0]["reason"] = "tampered"
        groups["DecodeError"].append("junk")
        again = q.dead_groups()
        self.assertEqual(len(again["DecodeError"]), 1)
        self.assertEqual(again["DecodeError"][0]["reason"], "DecodeError")


class TestGroupReplay(unittest.TestCase):
    def test_replay_only_one_pile_leaves_others_untouched(self):
        consumer = RoutingConsumer({})
        q = DeadLetterQueue(consumer, max_retries=1)
        sink(q, "d1", DecodeError)
        sink(q, "t1", TimeoutError)
        sink(q, "d2", DecodeError)

        # 只修了反序列化这一堆，超时那堆没修、不允许被搅和
        consumer.broken.pop("d1")
        consumer.broken.pop("d2")
        self.assertEqual(q.replay_group("DecodeError"), 2)

        groups = q.dead_groups()
        self.assertNotIn("DecodeError", groups)
        self.assertEqual([r["msg"]["id"]
                          for r in groups["TimeoutError"]], ["t1"])
        # 超时那组没参与重放：t1 只在最初沉底时被调过一次
        self.assertEqual(consumer.seen.count("t1"), 1)

    def test_replay_failure_keeps_original_pile_and_accumulates(self):
        consumer = RoutingConsumer({})
        q = DeadLetterQueue(consumer, max_retries=2)
        sink(q, "d1", DecodeError, payload={"n": 1})
        rec_before = q.dead_groups()["DecodeError"][0]
        self.assertEqual(rec_before["attempts"], 2)

        # 仍炸：退回原堆，attempts 接着往上加，绝不重置
        self.assertEqual(q.replay_group("DecodeError"), 0)
        rec_after = q.dead_groups()["DecodeError"][0]
        self.assertEqual(rec_after["attempts"], 3)
        self.assertEqual(rec_after["reason"], "DecodeError")
        self.assertEqual(rec_after["msg"]["payload"], {"n": 1})

        q.replay_group("DecodeError")
        self.assertEqual(q.dead_groups()["DecodeError"][0]["attempts"], 4)

    def test_replay_with_different_exception_returns_to_original_pile(self):
        consumer = RoutingConsumer({})
        q = DeadLetterQueue(consumer, max_retries=1)
        sink(q, "d1", DecodeError)
        # 重放时改抛超时，但仍要退回 DecodeError 原堆
        consumer.broken["d1"] = TimeoutError
        self.assertEqual(q.replay_group("DecodeError"), 0)
        groups = q.dead_groups()
        self.assertEqual(list(groups), ["DecodeError"])
        rec = groups["DecodeError"][0]
        self.assertEqual(rec["attempts"], 2)
        self.assertEqual(rec["error"], "boom d1")
        self.assertIsNotNone(rec["last_at"])

    def test_replay_unknown_group_returns_zero(self):
        q = DeadLetterQueue(RoutingConsumer({}), max_retries=1)
        self.assertEqual(q.replay_group("Nope"), 0)

    def test_replay_partial_recovery_keeps_order_within_pile(self):
        consumer = RoutingConsumer({})
        q = DeadLetterQueue(consumer, max_retries=1)
        sink(q, "d1", DecodeError)
        sink(q, "d2", DecodeError)
        sink(q, "d3", DecodeError)
        consumer.broken.pop("d2")  # 只修好中间这条
        self.assertEqual(q.replay_group("DecodeError"), 1)
        self.assertEqual(
            [r["msg"]["id"]
             for r in q.dead_groups()["DecodeError"]],
            ["d1", "d3"])


class TestRetention(unittest.TestCase):
    def test_sweep_archives_expired_with_clock_boundary(self):
        clock = ManualClock(0.0)
        q = DeadLetterQueue(RoutingConsumer({}), max_retries=1, clock=clock,
                            retention=10.0)
        sink(q, "d1", DecodeError)   # dead_at = 0
        clock.advance(9.0)
        sink(q, "t1", TimeoutError)  # dead_at = 9

        # 恰好到保留期边界（>=）：d1 age=10 归档，t1 age=1 还差一点
        clock.advance(1.0)
        self.assertEqual(q.sweep_retention(), 1)
        self.assertEqual(
            [r["msg"]["id"] for r in q.dead()], ["t1"])

        archived = q.archived("DecodeError")
        self.assertEqual(len(archived), 1)
        rec = archived[0]
        self.assertEqual(rec["msg"]["id"], "d1")
        self.assertEqual(rec["cause"], "ttl")
        self.assertEqual(rec["archived_at"], 10.0)

        # t1 dead_at=9，推到 19 才到期；按组照样能翻到
        clock.advance(9.0)
        q.sweep_retention()
        groups = q.archived()
        self.assertEqual(
            sorted(groups), ["DecodeError", "TimeoutError"])
        self.assertEqual(groups["TimeoutError"][0]["msg"]["id"], "t1")

    def test_no_retention_means_sweep_is_noop(self):
        q = DeadLetterQueue(RoutingConsumer({}), max_retries=1)
        sink(q, "d1", DecodeError)
        self.assertEqual(q.sweep_retention(), 0)
        self.assertEqual(len(q.dead()), 1)
        self.assertEqual(q.archived(), {})

    def test_retention_runs_before_new_dead_admission(self):
        clock = ManualClock(0.0)
        q = DeadLetterQueue(RoutingConsumer({}), max_retries=1, clock=clock,
                            retention=10.0)
        sink(q, "d1", DecodeError)  # dead_at = 0
        clock.advance(10.0)
        sink(q, "t1", TimeoutError)  # 入队即先清掉 d1

        self.assertEqual([r["msg"]["id"] for r in q.dead()], ["t1"])
        self.assertEqual(q.archived("DecodeError")[0]["cause"], "ttl")


class TestCapacity(unittest.TestCase):
    def test_overflow_moves_oldest_to_archive(self):
        clock = ManualClock(0.0)
        q = DeadLetterQueue(RoutingConsumer({}), max_retries=1, clock=clock,
                            max_dead=2)
        sink(q, "d1", DecodeError)
        sink(q, "t1", TimeoutError)
        sink(q, "d2", DecodeError)  # 挤出最老的 d1

        self.assertEqual([r["msg"]["id"] for r in q.dead()], ["t1", "d2"])
        archived = q.archived("DecodeError")
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0]["msg"]["id"], "d1")
        self.assertEqual(archived[0]["cause"], "capacity")
        self.assertEqual(archived[0]["archived_at"], 0.0)

    def test_retention_takes_precedence_over_capacity_eviction(self):
        clock = ManualClock(0.0)
        # 容量 2，保留期 10：d1 先被保留期清走，容量归档不再触发
        q = DeadLetterQueue(RoutingConsumer({}), max_retries=1, clock=clock,
                            retention=10.0, max_dead=2)
        sink(q, "d1", DecodeError)
        clock.advance(9.0)
        sink(q, "t1", TimeoutError)
        clock.advance(1.0)
        sink(q, "d2", DecodeError)  # 先 TTL 清 d1，d2 直接入队

        self.assertEqual(
            [r["msg"]["id"] for r in q.dead()], ["t1", "d2"])
        archived = q.archived()
        self.assertEqual(set(archived), {"DecodeError"})
        self.assertEqual(archived["DecodeError"][0]["cause"], "ttl")

    def test_archived_snapshots_are_copies(self):
        q = DeadLetterQueue(RoutingConsumer({}), max_retries=1, max_dead=1)
        sink(q, "d1", DecodeError)
        sink(q, "d2", DecodeError)
        snap = q.archived("DecodeError")
        snap[0]["cause"] = "tampered"
        self.assertEqual(q.archived("DecodeError")[0]["cause"], "capacity")


class TestConfigValidation(unittest.TestCase):
    def test_bad_retention_raises(self):
        with self.assertRaises(ValueError):
            DeadLetterQueue(RoutingConsumer({}), retention=0)

    def test_bad_max_dead_raises(self):
        with self.assertRaises(ValueError):
            DeadLetterQueue(RoutingConsumer({}), max_dead=0)


if __name__ == "__main__":
    unittest.main()
