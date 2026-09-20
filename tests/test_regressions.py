"""防回归测试：锁住四类历史问题的修复行为。

  1. 键只做去空白规范化，大小写不同的键是两笔不同的单
  2. finish 落盘，重启后键和结果都还在
  3. 占键后没收尾（处理中途失败）的键可以重新开工
  4. 过期从收尾时刻起算，不从占键时刻起算
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


class TestCaseSensitivity(unittest.TestCase):
    def test_keys_differing_only_by_case_are_distinct(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("Order-7001"))
        store.finish("Order-7001", {"amount": 100})
        self.assertTrue(store.begin("order-7001"))
        self.assertIsNone(store.get("order-7001"))

    def test_case_variant_results_do_not_leak(self):
        store = IdempotencyStore()
        store.finish("Pay-1", "upper")
        store.finish("pay-1", "lower")
        self.assertEqual(store.get("Pay-1"), "upper")
        self.assertEqual(store.get("pay-1"), "lower")

    def test_same_key_different_case_still_dedupes_itself(self):
        store = IdempotencyStore()
        store.finish("Pay-1", "receipt")
        self.assertFalse(store.begin("Pay-1"))


class TestPersistenceAcrossRestart(unittest.TestCase):
    def test_finished_result_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            before = IdempotencyStore(path=path)
            before.begin("pay-88")
            before.finish("pay-88", {"amount": 250, "state": "paid"})
            after = IdempotencyStore(path=path)
            self.assertEqual(after.get("pay-88"), {"amount": 250, "state": "paid"})

    def test_finished_key_still_dedupes_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            before = IdempotencyStore(path=path)
            before.begin("pay-88")
            before.finish("pay-88", "receipt")
            after = IdempotencyStore(path=path)
            self.assertFalse(after.begin("pay-88"))

    def test_finish_without_begin_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            IdempotencyStore(path=path).finish("solo", 42)
            self.assertEqual(IdempotencyStore(path=path).get("solo"), 42)


class TestHalfwayFailure(unittest.TestCase):
    def test_unfinished_key_can_be_retried(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("pay-99"))
        # 处理中途失败，finish 没被调用
        self.assertTrue(store.begin("pay-99"))

    def test_retried_key_completes_and_replays(self):
        store = IdempotencyStore()
        store.begin("pay-99")             # 第一次占键后失败
        self.assertTrue(store.begin("pay-99"))
        store.finish("pay-99", {"state": "paid"})
        self.assertEqual(store.get("pay-99"), {"state": "paid"})
        self.assertFalse(store.begin("pay-99"))

    def test_unfinished_key_returns_none_from_get(self):
        store = IdempotencyStore()
        store.begin("pay-99")
        self.assertIsNone(store.get("pay-99"))


class TestExpiryFromFinish(unittest.TestCase):
    def test_slow_request_result_survives_past_begin_plus_ttl(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-77")
        clock.advance(90)                 # 处理耗时超过 ttl
        store.finish("pay-77", {"amount": 300})
        self.assertEqual(store.get("pay-77"), {"amount": 300})

    def test_ttl_runs_from_finish_not_begin(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-77")
        clock.advance(50)
        store.finish("pay-77", "receipt")
        clock.advance(30)                 # 距开工 80 秒，距收工 30 秒
        self.assertEqual(store.get("pay-77"), "receipt")
        clock.advance(31)                 # 距收工 61 秒，过期
        self.assertIsNone(store.get("pay-77"))

    def test_expired_slow_key_can_be_processed_again(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-77")
        clock.advance(90)
        store.finish("pay-77", "first")
        clock.advance(61)
        self.assertTrue(store.begin("pay-77"))
        store.finish("pay-77", "second")
        self.assertEqual(store.get("pay-77"), "second")


if __name__ == "__main__":
    unittest.main()
