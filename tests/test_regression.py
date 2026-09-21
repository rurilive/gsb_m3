"""四类对账怪象与两个新能力的防回归测试。

对应 README 的 Known Issues：
  1. 大小写不同的键必须相互独立
  2. finish 必须落盘，重启后结果完整回放
  3. 处理失败用 fail() 释放占位，键可重新提交
  4. ttl 对已完成记录按完成时刻起算
另外覆盖：renew() 中途/完成后续期，max_result_size 截断标记。
"""

import json
import os
import tempfile
import unittest

from idemkey import IdempotencyStore, TruncatedResult


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestCaseSensitiveKeys(unittest.TestCase):
    """怪象 1：大小写只差一点的两个单号必须是两笔单子。"""

    def test_case_variant_is_a_new_key(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("Order-7001"))
        store.finish("Order-7001", {"amount": 100})
        self.assertTrue(store.begin("order-7001"))

    def test_case_variants_keep_independent_results(self):
        store = IdempotencyStore()
        store.finish("Order-7001", 100)
        store.finish("order-7001", 200)
        self.assertEqual(store.get("Order-7001"), 100)
        self.assertEqual(store.get("order-7001"), 200)

    def test_case_variants_both_play_back_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path)
            store.finish("Order-7001", 100)
            store.finish("order-7001", 200)
            reloaded = IdempotencyStore(path=path)
            self.assertEqual(reloaded.get("Order-7001"), 100)
            self.assertEqual(reloaded.get("order-7001"), 200)


class TestPersistenceAfterFinish(unittest.TestCase):
    """怪象 2：finish 的结果必须落盘，重启后不能只剩空占位。"""

    def test_finished_result_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            receipt = {"amount": 250, "state": "paid"}
            before = IdempotencyStore(path=path)
            before.begin("pay-88")
            before.finish("pay-88", receipt)
            after = IdempotencyStore(path=path)
            self.assertEqual(after.get("pay-88"), receipt)
            self.assertFalse(after.begin("pay-88"))

    def test_finish_without_begin_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            IdempotencyStore(path=path).finish("solo", 42)
            self.assertEqual(IdempotencyStore(path=path).get("solo"), 42)

    def test_unfinished_placeholder_is_dropped_on_restart(self):
        # 模拟进程崩在 begin 之后、finish 之前：磁盘上残留空占位，
        # 重启后必须允许同一键重新处理，而不是永久判重回空。
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "pay-x": {
                            "result": None,
                            "created_at": 1.0,
                            "finished_at": None,
                        }
                    },
                    fh,
                )
            store = IdempotencyStore(path=path)
            self.assertIsNone(store.get("pay-x"))
            self.assertTrue(store.begin("pay-x"))


class TestFailReleasesKey(unittest.TestCase):
    """怪象 3：中途失败必须能释放占位，重发可以开工。"""

    def test_fail_frees_reservation(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("pay-99"))
        self.assertTrue(store.fail("pay-99"))
        self.assertIsNone(store.get("pay-99"))
        self.assertTrue(store.begin("pay-99"))

    def test_retry_after_fail_finishes_and_plays_back(self):
        store = IdempotencyStore()
        attempts = {"n": 0}

        def do_work():
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("下游超时")
            return {"state": "paid"}

        def submit():
            if not store.begin("pay-99"):
                return store.get("pay-99"), False
            try:
                result = do_work()
            except RuntimeError:
                store.fail("pay-99")
                raise
            store.finish("pay-99", result)
            return result, True

        with self.assertRaises(RuntimeError):
            submit()
        result, handled = submit()
        self.assertTrue(handled)
        self.assertEqual(result, {"state": "paid"})
        self.assertEqual(store.get("pay-99"), {"state": "paid"})
        self.assertFalse(store.begin("pay-99"))

    def test_fail_does_not_touch_finished_result(self):
        store = IdempotencyStore()
        store.finish("pay-1", "receipt")
        self.assertFalse(store.fail("pay-1"))
        self.assertEqual(store.get("pay-1"), "receipt")
        self.assertFalse(store.begin("pay-1"))

    def test_fail_unknown_key_returns_false(self):
        store = IdempotencyStore()
        self.assertFalse(store.fail("nope"))

    def test_fail_persists_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path)
            store.begin("pay-2")
            self.assertTrue(store.fail("pay-2"))
            reloaded = IdempotencyStore(path=path)
            self.assertTrue(reloaded.begin("pay-2"))


class TestTtlFromCompletion(unittest.TestCase):
    """怪象 4：已完成记录的 ttl 从完成时刻起算。"""

    def test_long_running_request_survives_past_finish(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-77")
        clock.advance(90)
        store.finish("pay-77", {"amount": 300})
        self.assertEqual(store.get("pay-77"), {"amount": 300})
        self.assertFalse(store.begin("pay-77"))

    def test_finished_record_expires_one_ttl_after_finish(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-77")
        clock.advance(90)
        store.finish("pay-77", "receipt")
        clock.advance(59)
        self.assertEqual(store.get("pay-77"), "receipt")
        clock.advance(2)
        self.assertIsNone(store.get("pay-77"))

    def test_unfinished_placeholder_still_expires_from_creation(self):
        # worker 死掉、没人 fail 时，占位超过 ttl 必须能被新请求接管。
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("zombie")
        clock.advance(61)
        self.assertTrue(store.begin("zombie"))


class TestRenew(unittest.TestCase):
    """新能力：处理中与完成后的续期。"""

    def test_renew_in_flight_keeps_long_request_alive(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-66")
        clock.advance(55)
        self.assertTrue(store.renew("pay-66"))
        clock.advance(55)
        store.finish("pay-66", {"amount": 88})
        self.assertEqual(store.get("pay-66"), {"amount": 88})

    def test_renew_after_finish_extends_playback_window(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-66")
        store.finish("pay-66", "receipt")
        clock.advance(55)
        self.assertTrue(store.renew("pay-66"))
        clock.advance(40)
        self.assertEqual(store.get("pay-66"), "receipt")
        clock.advance(21)
        self.assertIsNone(store.get("pay-66"))

    def test_renew_unknown_key_returns_false(self):
        store = IdempotencyStore()
        self.assertFalse(store.renew("nope"))

    def test_renew_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path)
            store.finish("pay-3", "receipt")
            self.assertTrue(store.renew("pay-3"))
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            self.assertEqual(
                raw["pay-3"]["created_at"], raw["pay-3"]["finished_at"]
            )
            self.assertEqual(
                IdempotencyStore(path=path).get("pay-3"), "receipt"
            )


class TestTruncatedResult(unittest.TestCase):
    """新能力：结果超上限落截断标记。"""

    def test_small_result_is_stored_as_is(self):
        store = IdempotencyStore(max_result_size=1000)
        store.finish("k", {"a": 1})
        self.assertEqual(store.get("k"), {"a": 1})

    def test_oversized_result_becomes_marker(self):
        store = IdempotencyStore(max_result_size=32)
        big = {"receipt": "X" * 200}
        store.finish("k", big)
        got = store.get("k")
        self.assertIsInstance(got, TruncatedResult)
        self.assertGreater(got.original_size, 32)
        self.assertEqual(got.limit, 32)
        self.assertTrue(got.preview)
        self.assertLessEqual(len(got.preview.encode("utf-8")), 32)

    def test_truncated_key_still_counts_as_processed(self):
        store = IdempotencyStore(max_result_size=32)
        store.finish("k", {"receipt": "X" * 200})
        self.assertFalse(store.begin("k"))
        first = store.get("k")
        second = store.get("k")
        self.assertEqual(first, second)

    def test_truncated_marker_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path, max_result_size=32)
            store.finish("k", {"receipt": "X" * 200})
            reloaded = IdempotencyStore(path=path, max_result_size=32)
            got = reloaded.get("k")
            self.assertIsInstance(got, TruncatedResult)
            self.assertEqual(got, store.get("k"))

    def test_invalid_max_result_size_raises(self):
        with self.assertRaises(ValueError):
            IdempotencyStore(max_result_size=0)


if __name__ == "__main__":
    unittest.main()
