"""单锁全局计数器的锁定测试。

本文件把改造之前的 ShardCounter 行为一字锁死：incr 的默认步长与
自定义步长、get 读到的是累加后的值、负增量语义、reset 回到刚建立
时的状态、非法步长在入口处报错、以及并发 incr 下计数不丢。新增的
分片、快照、滑动窗口、上限等能力另开测试文件，本文件一字不改。
"""

import threading
import unittest

from shardcount.counter import ShardCounter


class TestCounterArithmetic(unittest.TestCase):
    def test_new_counter_is_zero(self):
        self.assertEqual(ShardCounter().get(), 0)

    def test_incr_default_step_is_one(self):
        c = ShardCounter()
        c.incr()
        self.assertEqual(c.get(), 1)

    def test_incr_by_explicit_step(self):
        c = ShardCounter()
        c.incr(5)
        self.assertEqual(c.get(), 5)

    def test_incr_accumulates(self):
        c = ShardCounter()
        for _ in range(7):
            c.incr()
        self.assertEqual(c.get(), 7)

    def test_incr_accepts_float_step(self):
        c = ShardCounter()
        c.incr(0.5)
        c.incr(0.25)
        self.assertEqual(c.get(), 0.75)

    def test_incr_accepts_negative_step(self):
        c = ShardCounter()
        c.incr(10)
        c.incr(-4)
        self.assertEqual(c.get(), 6)

    def test_incr_by_zero_keeps_value(self):
        c = ShardCounter()
        c.incr(3)
        c.incr(0)
        self.assertEqual(c.get(), 3)

    def test_get_is_stable_without_incr(self):
        c = ShardCounter()
        c.incr(2)
        self.assertEqual(c.get(), c.get())


class TestCounterReset(unittest.TestCase):
    def test_reset_clears_value(self):
        c = ShardCounter()
        c.incr(9)
        c.reset()
        self.assertEqual(c.get(), 0)

    def test_reset_only_affects_incr_before_it(self):
        c = ShardCounter()
        c.incr(4)
        c.reset()
        c.incr(1)
        self.assertEqual(c.get(), 1)

    def test_reset_then_reuse_matches_fresh(self):
        c = ShardCounter()
        c.incr(100)
        c.reset()
        fresh = ShardCounter()
        self.assertEqual(c.get(), fresh.get())


class TestCounterRejectsBadInput(unittest.TestCase):
    def test_incr_rejects_text(self):
        with self.assertRaises(TypeError):
            ShardCounter().incr("3")

    def test_incr_rejects_none(self):
        with self.assertRaises(TypeError):
            ShardCounter().incr(None)

    def test_incr_rejects_containers(self):
        with self.assertRaises(TypeError):
            ShardCounter().incr([1])

    def test_incr_rejects_bool(self):
        with self.assertRaises(TypeError):
            ShardCounter().incr(True)

    def test_rejected_step_does_not_change_state(self):
        c = ShardCounter()
        c.incr(2)
        with self.assertRaises(TypeError):
            c.incr("not a number")
        self.assertEqual(c.get(), 2)


class TestCounterConcurrency(unittest.TestCase):
    def test_concurrent_incr_loses_nothing(self):
        c = ShardCounter()
        threads = []

        def worker():
            for _ in range(1000):
                c.incr()

        for _ in range(8):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(c.get(), 8000)

    def test_concurrent_incr_with_steps_matches_sum(self):
        c = ShardCounter()
        threads = []

        def worker(step):
            for _ in range(500):
                c.incr(step)

        steps = [1, 2, 3, 4]
        for s in steps:
            t = threading.Thread(target=worker, args=(s,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(c.get(), sum(s * 500 for s in steps))


if __name__ == "__main__":
    unittest.main()
