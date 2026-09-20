"""DeadLetterQueue 分组、定向重放与归档的测试。"""

import unittest

from deadletter.queue import DeadLetterQueue


class FakeClock:
    """可手动推进的注入时钟。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


class TypedConsumer:
    """按 id 抛指定异常的可注入消费者；errors 里没有的 id 视为成功。"""

    def __init__(self, errors):
        self.errors = dict(errors)
        self.seen = []

    def __call__(self, msg):
        self.seen.append(msg["id"])
        exc = self.errors.get(msg["id"])
        if exc is not None:
            raise exc("downstream rejected %s" % msg["id"])


def msg(mid, payload=None):
    return {"id": mid, "payload": payload if payload is not None else mid}


class TestGrouping(unittest.TestCase):
    def test_dead_letters_group_by_exception_type(self):
        consumer = TypedConsumer({"a": ValueError, "b": TimeoutError,
                                  "c": ValueError})
        q = DeadLetterQueue(consumer, max_retries=1)
        for mid in ("a", "b", "c"):
            q.consume(msg(mid))
        self.assertEqual(q.groups(), ["TimeoutError", "ValueError"])
        self.assertEqual(
            [r["msg"]["id"] for r in q.dead_group("ValueError")], ["a", "c"])
        self.assertEqual(
            [r["msg"]["id"] for r in q.dead_group("TimeoutError")], ["b"])

    def test_group_records_carry_payload_and_context(self):
        q = DeadLetterQueue(TypedConsumer({"a": ValueError}), max_retries=2,
                            clock=lambda: 1000.0)
        q.consume(msg("a", payload={"n": 7}))
        q.consume(msg("a", payload={"n": 7}))
        rec = q.dead_group("ValueError")[0]
        self.assertEqual(rec["msg"]["payload"], {"n": 7})
        self.assertEqual(rec["reason"], "ValueError")
        self.assertEqual(rec["detail"], "downstream rejected a")
        self.assertEqual(rec["attempts"], 2)
        self.assertEqual(rec["dead_at"], 1000.0)

    def test_dead_group_returns_copies(self):
        q = DeadLetterQueue(TypedConsumer({"a": ValueError}), max_retries=1)
        q.consume(msg("a"))
        snapshot = q.dead_group("ValueError")
        snapshot[0]["reason"] = "tampered"
        self.assertEqual(q.dead_group("ValueError")[0]["reason"], "ValueError")

    def test_unknown_group_is_empty(self):
        q = DeadLetterQueue(TypedConsumer({"a": ValueError}), max_retries=1)
        q.consume(msg("a"))
        self.assertEqual(q.dead_group("KeyError"), [])


class TestGroupReplay(unittest.TestCase):
    def test_replay_only_touches_target_group(self):
        consumer = TypedConsumer({"a": ValueError, "b": TimeoutError})
        q = DeadLetterQueue(consumer, max_retries=1)
        q.consume(msg("a"))
        q.consume(msg("b"))
        consumer.seen.clear()
        del consumer.errors["a"]          # 只修好 ValueError 那堆
        self.assertEqual(q.replay("ValueError"), 1)
        self.assertEqual(consumer.seen, ["a"])   # 别的组没被重放
        self.assertEqual(q.groups(), ["TimeoutError"])
        self.assertEqual([r["msg"]["id"] for r in q.dead()], ["b"])

    def test_replay_failure_returns_to_same_group_and_counts_up(self):
        consumer = TypedConsumer({"a": ValueError})
        q = DeadLetterQueue(consumer, max_retries=2, clock=lambda: 1000.0)
        q.consume(msg("a"))
        q.consume(msg("a"))               # attempts=2 沉淀
        self.assertEqual(q.replay("ValueError"), 0)
        rec = q.dead_group("ValueError")[0]
        self.assertEqual(rec["attempts"], 3)      # 接着往上加，不清零
        self.assertEqual(rec["dead_at"], 1000.0)  # 沉淀时刻保持原值
        self.assertEqual(q.replay("ValueError"), 0)
        self.assertEqual(q.dead_group("ValueError")[0]["attempts"], 4)

    def test_replay_recovers_after_consumer_fixed(self):
        consumer = TypedConsumer({"a": ValueError})
        q = DeadLetterQueue(consumer, max_retries=1)
        q.consume(msg("a"))
        consumer.errors.clear()
        self.assertEqual(q.replay("ValueError"), 1)
        self.assertEqual(q.dead(), [])
        self.assertEqual(q.groups(), [])

    def test_replay_unknown_group_is_noop(self):
        q = DeadLetterQueue(TypedConsumer({"a": ValueError}), max_retries=1)
        q.consume(msg("a"))
        self.assertEqual(q.replay("TimeoutError"), 0)
        self.assertEqual(len(q.dead()), 1)


class TestRetentionSweep(unittest.TestCase):
    def test_expired_dead_letters_are_archived_at_sweep(self):
        clock = FakeClock(100.0)
        q = DeadLetterQueue(TypedConsumer({"a": ValueError}), max_retries=1,
                            retention=50.0, clock=clock)
        q.consume(msg("a"))               # dead_at=100.0
        clock.advance(49.0)               # now=149.0，未到期
        self.assertEqual(q.sweep(), 0)
        self.assertEqual(len(q.dead()), 1)
        clock.advance(1.0)                # now=150.0，达到保留期
        self.assertEqual(q.sweep(), 1)
        self.assertEqual(q.dead(), [])
        archived = q.archived()
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0]["msg"]["id"], "a")
        self.assertEqual(archived[0]["dead_at"], 100.0)
        self.assertEqual(archived[0]["archived_at"], 150.0)
        self.assertEqual(archived[0]["cause"], "expired")

    def test_archive_is_queryable_by_group(self):
        clock = FakeClock(0.0)
        consumer = TypedConsumer({"a": ValueError, "b": TimeoutError})
        q = DeadLetterQueue(consumer, max_retries=1, retention=10.0,
                            clock=clock)
        q.consume(msg("a"))
        q.consume(msg("b"))
        clock.advance(10.0)
        q.sweep()
        self.assertEqual([r["msg"]["id"] for r in q.archived("ValueError")],
                         ["a"])
        self.assertEqual([r["msg"]["id"] for r in q.archived("TimeoutError")],
                         ["b"])
        self.assertEqual(len(q.archived()), 2)

    def test_replayed_failure_keeps_original_dead_at_for_retention(self):
        clock = FakeClock(100.0)
        consumer = TypedConsumer({"a": ValueError})
        q = DeadLetterQueue(consumer, max_retries=1, retention=50.0,
                            clock=clock)
        q.consume(msg("a"))               # dead_at=100.0
        clock.advance(40.0)               # now=140.0
        self.assertEqual(q.replay("ValueError"), 0)  # 退回原组，dead_at 不变
        clock.advance(10.0)               # now=150.0，按原 dead_at 到期
        self.assertEqual(q.sweep(), 1)
        self.assertEqual(q.archived()[0]["attempts"], 2)


class TestCapacity(unittest.TestCase):
    def test_oldest_overflows_to_archive_when_full(self):
        clock = FakeClock(100.0)
        consumer = TypedConsumer({"a": ValueError, "b": ValueError,
                                  "c": ValueError})
        q = DeadLetterQueue(consumer, max_retries=1, capacity=2, clock=clock)
        q.consume(msg("a"))
        q.consume(msg("b"))
        clock.advance(5.0)
        q.consume(msg("c"))               # sweep 前允许暂时超出容量
        self.assertEqual(len(q.dead()), 3)
        clock.advance(5.0)                # now=110.0
        self.assertEqual(q.sweep(), 1)    # 超容量，最老的 a 挪入归档
        self.assertEqual([r["msg"]["id"] for r in q.dead()], ["b", "c"])
        archived = q.archived()
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0]["msg"]["id"], "a")
        self.assertEqual(archived[0]["cause"], "overflow")
        self.assertEqual(archived[0]["archived_at"], 110.0)

    def test_sweep_applies_retention_before_capacity(self):
        clock = FakeClock(0.0)
        consumer = TypedConsumer({"a": ValueError, "b": TimeoutError})
        q = DeadLetterQueue(consumer, max_retries=1, retention=10.0,
                            capacity=1, clock=clock)
        clock.advance(100.0)              # now=100.0
        q.consume(msg("a"))               # dead_at=100.0
        clock.advance(10.0)               # now=110.0，a 到期
        q.consume(msg("b"))               # dead_at=110.0，容量挤占留给 sweep
        self.assertEqual(len(q.dead()), 2)
        self.assertEqual(q.sweep(), 1)    # 先按保留期清走 a，容量已不超限
        archived = q.archived()
        self.assertEqual(archived[0]["msg"]["id"], "a")
        self.assertEqual(archived[0]["cause"], "expired")
        self.assertEqual(archived[0]["archived_at"], 110.0)
        self.assertEqual([r["msg"]["id"] for r in q.dead()], ["b"])

    def test_archived_returns_copies(self):
        consumer = TypedConsumer({"a": ValueError, "b": ValueError})
        q = DeadLetterQueue(consumer, max_retries=1, capacity=1)
        q.consume(msg("a"))
        q.consume(msg("b"))
        q.sweep()                         # 最老的 a 被挤入归档
        snapshot = q.archived()
        snapshot[0]["cause"] = "tampered"
        self.assertEqual(q.archived()[0]["cause"], "overflow")


class TestConfigValidation(unittest.TestCase):
    def test_invalid_retention_raises(self):
        with self.assertRaises(ValueError):
            DeadLetterQueue(TypedConsumer({}), retention=0)

    def test_invalid_capacity_raises(self):
        with self.assertRaises(ValueError):
            DeadLetterQueue(TypedConsumer({}), capacity=0)


if __name__ == "__main__":
    unittest.main()
