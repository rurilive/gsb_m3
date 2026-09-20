"""四类线上事故的防回归测试。

对应 README Known Issues 里的四条：
  1. 只差大小写的单号被并键，后一笔拿回前一笔的回执
  2. 服务重启后键还在、结果丢失，重发被判成重复却取不到结果
  3. 处理中途失败后键被卡死，永远返回空结果
  4. 有效期从开工时刻起算，耗时单收工即被清掉
"""

import os
import tempfile
import unittest

from idemkey import IdempotencyStore


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestCaseSensitiveKeys(unittest.TestCase):
    def test_keys_differing_only_in_case_are_distinct(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("Order-7001"))
        store.finish("Order-7001", {"amount": 100})
        self.assertTrue(store.begin("order-7001"))
        store.finish("order-7001", {"amount": 40})
        self.assertEqual(store.get("Order-7001"), {"amount": 100})
        self.assertEqual(store.get("order-7001"), {"amount": 40})

    def test_same_key_still_dedupes(self):
        store = IdempotencyStore()
        store.finish("Order-7001", "receipt")
        self.assertFalse(store.begin("Order-7001"))
        self.assertEqual(store.get("Order-7001"), "receipt")


class TestRestartKeepsResults(unittest.TestCase):
    def test_finished_result_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            before = IdempotencyStore(path=path)
            before.begin("pay-88")
            before.finish("pay-88", {"amount": 250, "state": "paid"})
            after = IdempotencyStore(path=path)
            self.assertEqual(after.get("pay-88"), {"amount": 250, "state": "paid"})
            self.assertFalse(after.begin("pay-88"))

    def test_finish_without_begin_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            IdempotencyStore(path=path).finish("solo", 42)
            self.assertEqual(IdempotencyStore(path=path).get("solo"), 42)


class TestFailedAttemptCanRetry(unittest.TestCase):
    def test_unfinished_key_can_begin_again(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("pay-99"))
        # 处理中途失败，finish 没有被调用
        self.assertTrue(store.begin("pay-99"))
        store.finish("pay-99", {"state": "paid"})
        self.assertEqual(store.get("pay-99"), {"state": "paid"})
        self.assertFalse(store.begin("pay-99"))

    def test_get_on_unfinished_key_still_returns_none(self):
        store = IdempotencyStore()
        store.begin("pay-99")
        self.assertIsNone(store.get("pay-99"))


class TestExpiryCountsFromFinish(unittest.TestCase):
    def test_ttl_starts_at_finish_not_begin(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-77")
        clock.advance(90)  # 处理耗时超过 ttl
        store.finish("pay-77", {"amount": 300})
        self.assertEqual(store.get("pay-77"), {"amount": 300})
        self.assertFalse(store.begin("pay-77"))

    def test_record_expires_ttl_after_finish(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-77")
        clock.advance(90)
        store.finish("pay-77", {"amount": 300})
        clock.advance(59)
        self.assertEqual(store.get("pay-77"), {"amount": 300})
        clock.advance(2)
        self.assertIsNone(store.get("pay-77"))
        self.assertTrue(store.begin("pay-77"))


if __name__ == "__main__":
    unittest.main()
