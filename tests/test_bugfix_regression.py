"""防回归测试：覆盖重复消费、TTL 过期、实例隔离、空载荷四类历史缺陷。"""

import unittest

from dedupq import DedupQueue, FakeClock


class RedeliveryDedupTest(unittest.TestCase):
    """pop 消费后，去重记录在 TTL 内必须仍然有效。"""

    def test_redelivery_rejected_after_consume(self):
        clock = FakeClock(0.0)
        q = DedupQueue(ttl=60.0, clock=clock)
        self.assertTrue(q.submit("pay-1", {"amount": 100}))
        self.assertEqual(q.pop(), ("pay-1", {"amount": 100}))
        self.assertFalse(q.submit("pay-1", {"amount": 100}))
        self.assertEqual(q.size(), 0)
        self.assertIsNone(q.pop())

    def test_redelivery_rejected_until_ttl_passes(self):
        clock = FakeClock(0.0)
        q = DedupQueue(ttl=10.0, clock=clock)
        q.submit("pay-2", {"amount": 1})
        q.pop()
        clock.advance(9.9)
        self.assertFalse(q.submit("pay-2", {"amount": 1}))
        clock.advance(0.2)
        self.assertTrue(q.submit("pay-2", {"amount": 1}))


class TtlExpiryTest(unittest.TestCase):
    """去重记录按 TTL 过期，过期后同一 id 可再次入队。"""

    def test_expired_record_allows_resubmit_after_consume(self):
        clock = FakeClock(0.0)
        q = DedupQueue(ttl=5.0, clock=clock)
        q.submit("t1", "x")
        q.pop()
        clock.advance(6.0)
        self.assertTrue(q.submit("t1", "x"))
        self.assertEqual(q.pop(), ("t1", "x"))

    def test_cleanup_frees_expired_records(self):
        clock = FakeClock(0.0)
        q = DedupQueue(ttl=5.0, clock=clock)
        q.submit("t2", None)
        q.pop()
        clock.advance(6.0)
        q.cleanup()
        self.assertEqual(len(q._seen), 0)

    def test_consumed_payload_not_retained(self):
        clock = FakeClock(0.0)
        q = DedupQueue(ttl=60.0, clock=clock)
        q.submit("t3", {"big": "payload"})
        q.pop()
        self.assertEqual(len(q._payload), 0)


class InstanceIsolationTest(unittest.TestCase):
    """多个 DedupQueue 实例的去重状态必须互不影响。"""

    def test_instances_do_not_share_seen_state(self):
        clock = FakeClock(0.0)
        qa = DedupQueue(ttl=60.0, clock=clock)
        qb = DedupQueue(ttl=60.0, clock=clock)
        self.assertTrue(qa.submit("shared-id", {"w": "a"}))
        self.assertTrue(qb.submit("shared-id", {"w": "b"}))
        self.assertEqual(qa.pop(), ("shared-id", {"w": "a"}))
        self.assertEqual(qb.pop(), ("shared-id", {"w": "b"}))

    def test_default_instances_do_not_share_seen_state(self):
        qa = DedupQueue()
        qb = DedupQueue()
        qa.submit("k", None)
        self.assertTrue(qb.submit("k", None))


class EmptyPayloadTest(unittest.TestCase):
    """不带载荷的心跳消息必须能正常入队、查看、消费。"""

    def test_submit_and_pop_without_payload(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        self.assertTrue(q.submit("heartbeat-1"))
        self.assertEqual(q.peek(), ("heartbeat-1", None))
        self.assertEqual(q.pop(), ("heartbeat-1", None))
        self.assertIsNone(q.pop())

    def test_heartbeat_does_not_block_following_messages(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        q.submit("hb")
        q.submit("biz-1", {"body": 1})
        self.assertEqual(q.pop(), ("hb", None))
        self.assertEqual(q.pop(), ("biz-1", {"body": 1}))

    def test_explicit_none_payload_roundtrip(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        q.submit("hb-2", None)
        self.assertEqual(q.pop(), ("hb-2", None))


if __name__ == "__main__":
    unittest.main()
