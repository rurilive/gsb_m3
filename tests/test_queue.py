"""DeadLetterQueue 现有行为的锁定测试。"""

import unittest

from deadletter.queue import DeadLetterQueue


class FakeConsumer:
    """可切换成功与失败的可注入消费者。

    broken 集合里的 id 会抛 ValueError；调用方随时改动它来模拟下游修复。
    """

    def __init__(self, broken):
        self.broken = set(broken)
        self.seen = []

    def __call__(self, msg):
        self.seen.append(msg["id"])
        if msg["id"] in self.broken:
            raise ValueError("downstream rejected %s" % msg["id"])


def msg(mid, payload=None):
    return {"id": mid, "payload": payload if payload is not None else mid}


class TestDeadLetterQueue(unittest.TestCase):
    def test_success_returns_true_and_leaves_no_dead(self):
        q = DeadLetterQueue(FakeConsumer([]), max_retries=2)
        self.assertTrue(q.consume(msg("a")))
        self.assertEqual(q.dead(), [])

    def test_failure_below_limit_sits_in_attempts_not_dead(self):
        q = DeadLetterQueue(FakeConsumer(["a"]), max_retries=3)
        self.assertFalse(q.consume(msg("a")))
        self.assertFalse(q.consume(msg("a")))
        self.assertEqual(q.dead(), [])

    def test_failure_reaching_limit_lands_in_dead(self):
        q = DeadLetterQueue(FakeConsumer(["a"]), max_retries=3)
        for _ in range(3):
            q.consume(msg("a"))
        dead = q.dead()
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0]["msg"]["id"], "a")

    def test_record_carries_attempts_reason_and_clock(self):
        q = DeadLetterQueue(FakeConsumer(["a"]), max_retries=2,
                            clock=lambda: 1000.0)
        q.consume(msg("a"))
        q.consume(msg("a"))
        rec = q.dead()[0]
        self.assertEqual(rec["attempts"], 2)
        self.assertEqual(rec["reason"], "ValueError")
        self.assertEqual(rec["dead_at"], 1000.0)

    def test_success_resets_failure_streak(self):
        consumer = FakeConsumer(["a"])
        q = DeadLetterQueue(consumer, max_retries=2)
        q.consume(msg("a"))          # 失败 1 次
        consumer.broken.clear()
        self.assertTrue(q.consume(msg("a")))   # 成功，计数清零
        consumer.broken.add("a")
        q.consume(msg("a"))          # 重新算作失败 1 次，不该进死信
        self.assertEqual(q.dead(), [])

    def test_dead_returns_copies(self):
        q = DeadLetterQueue(FakeConsumer(["a"]), max_retries=1)
        q.consume(msg("a"))
        snapshot = q.dead()
        snapshot[0]["reason"] = "tampered"
        snapshot.append({"msg": msg("b")})
        self.assertEqual(len(q.dead()), 1)
        self.assertEqual(q.dead()[0]["reason"], "ValueError")

    def test_dead_keeps_payload(self):
        q = DeadLetterQueue(FakeConsumer(["a"]), max_retries=1)
        q.consume(msg("a", payload={"n": 7}))
        self.assertEqual(q.dead()[0]["msg"]["payload"], {"n": 7})

    def test_retry_dead_recovers_when_consumer_fixed(self):
        consumer = FakeConsumer(["a"])
        q = DeadLetterQueue(consumer, max_retries=1)
        q.consume(msg("a"))
        self.assertEqual(len(q.dead()), 1)
        consumer.broken.clear()
        self.assertEqual(q.retry_dead(), 1)
        self.assertEqual(q.dead(), [])
        self.assertIn("a", consumer.seen)

    def test_retry_dead_keeps_still_failing_message(self):
        q = DeadLetterQueue(FakeConsumer(["a"]), max_retries=1)
        q.consume(msg("a"))
        self.assertEqual(q.retry_dead(), 0)
        self.assertEqual(len(q.dead()), 1)

    def test_retry_dead_counts_mixed_outcomes(self):
        consumer = FakeConsumer(["a", "b"])
        q = DeadLetterQueue(consumer, max_retries=1)
        q.consume(msg("a"))
        q.consume(msg("b"))
        consumer.broken.clear()
        consumer.broken.add("b")     # b 仍坏
        self.assertEqual(q.retry_dead(), 1)
        remaining = q.dead()
        self.assertEqual([r["msg"]["id"] for r in remaining], ["b"])

    def test_clock_is_injectable(self):
        ticks = iter([10.0, 20.0])
        q = DeadLetterQueue(FakeConsumer(["a", "b"]), max_retries=1,
                            clock=lambda: next(ticks))
        q.consume(msg("a"))
        q.consume(msg("b"))
        self.assertEqual([r["dead_at"] for r in q.dead()], [10.0, 20.0])

    def test_invalid_max_retries_raises(self):
        with self.assertRaises(ValueError):
            DeadLetterQueue(FakeConsumer([]), max_retries=0)


if __name__ == "__main__":
    unittest.main()
