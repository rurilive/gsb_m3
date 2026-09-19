"""delayq 防回归测试：覆盖上线反馈的四个现象。

运行方式：python3 -m unittest discover -s tests -v
"""
import unittest

from delayq import DelayedQueue, FakeClock


def drain(q):
    """弹出并执行当前所有已到期任务，返回执行的任务体结果列表。"""
    ran = []
    while True:
        task = q.pop_ready()
        if task is None:
            return ran
        ran.append(task())


class PopReadyTest(unittest.TestCase):
    """现象 1：还没到点的任务被提前捞出来执行。"""

    def test_not_due_task_is_not_popped(self):
        clock = FakeClock(start=100.0)
        q = DelayedQueue(clock=clock)
        q.add(lambda: "x", delay=5.0)
        clock.advance(4.999)
        self.assertIsNone(q.pop_ready())
        self.assertEqual(len(q), 1)

    def test_task_pops_exactly_at_due(self):
        clock = FakeClock(start=100.0)
        q = DelayedQueue(clock=clock)
        q.add(lambda: "x", delay=5.0)
        clock.advance(5.0)
        self.assertEqual(drain(q), ["x"])
        self.assertEqual(len(q), 0)

    def test_empty_queue_pop_returns_none(self):
        q = DelayedQueue(clock=FakeClock())
        self.assertIsNone(q.pop_ready())

    def test_negative_delay_rejected(self):
        q = DelayedQueue(clock=FakeClock())
        with self.assertRaises(ValueError):
            q.add(lambda: None, delay=-0.1)


class OrderingTest(unittest.TestCase):
    """现象 2：同一时刻到期的任务执行顺序飘忽。"""

    def test_same_due_pops_in_submission_order(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        for i in range(20):
            q.add(lambda i=i: i, delay=1.0)
        clock.advance(1.0)
        self.assertEqual(drain(q), list(range(20)))

    def test_same_due_fifo_is_stable_across_runs(self):
        for _ in range(5):
            self.test_same_due_pops_in_submission_order()

    def test_earlier_due_pops_first_regardless_of_submission_order(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        q.add(lambda: "late", delay=10.0)
        q.add(lambda: "early", delay=1.0)
        q.add(lambda: "mid", delay=5.0)
        clock.advance(10.0)
        self.assertEqual(drain(q), ["early", "mid", "late"])


class DedupTest(unittest.TestCase):
    """现象 3：同一 key 重复提交，旧条目到期后照样被执行。"""

    def test_duplicate_key_only_latest_runs(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        q.add(lambda: "old", delay=1.0, key="k")
        q.add(lambda: "new", delay=1.0, key="k")
        clock.advance(1.0)
        self.assertEqual(drain(q), ["new"])
        self.assertEqual(len(q), 0)

    def test_voided_entry_not_counted_in_len(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        q.add(lambda: None, delay=1.0, key="k")
        q.add(lambda: None, delay=2.0, key="k")
        self.assertEqual(len(q), 1)

    def test_key_can_be_reused_after_pop(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        q.add(lambda: "first", delay=1.0, key="k")
        clock.advance(1.0)
        self.assertEqual(drain(q), ["first"])
        q.add(lambda: "second", delay=1.0, key="k")
        clock.advance(1.0)
        self.assertEqual(drain(q), ["second"])

    def test_distinct_keys_do_not_interfere(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        q.add(lambda: "a", delay=1.0, key="ka")
        q.add(lambda: "b", delay=1.0, key="kb")
        clock.advance(1.0)
        self.assertEqual(drain(q), ["a", "b"])


class PeekTest(unittest.TestCase):
    """现象 4：peek 返回值导致消费端空转或睡过头。"""

    def test_peek_returns_remaining_wait_not_absolute_due(self):
        clock = FakeClock(start=1000.0)
        q = DelayedQueue(clock=clock)
        q.add(lambda: None, delay=5.0)
        self.assertAlmostEqual(q.peek(), 5.0)
        clock.advance(2.0)
        self.assertAlmostEqual(q.peek(), 3.0)

    def test_peek_clamps_to_zero_when_overdue(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        q.add(lambda: None, delay=1.0)
        clock.advance(2.0)
        self.assertEqual(q.peek(), 0.0)

    def test_peek_none_when_empty(self):
        q = DelayedQueue(clock=FakeClock())
        self.assertIsNone(q.peek())

    def test_peek_skips_voided_entries(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        q.add(lambda: None, delay=1.0, key="k")
        q.add(lambda: None, delay=10.0, key="k")
        self.assertAlmostEqual(q.peek(), 10.0)


class ConsumerLoopTest(unittest.TestCase):
    """端到端：按 peek 睡眠再轮询的消费循环，不快进、不空转。"""

    def test_consume_loop_sleeps_exactly_and_runs_on_time(self):
        clock = FakeClock(start=50.0)
        q = DelayedQueue(clock=clock)
        ran = []
        q.add(lambda: ran.append(("A", clock.monotonic())), delay=2.0)
        q.add(lambda: ran.append(("B", clock.monotonic())), delay=2.0)
        q.add(lambda: ran.append(("C", clock.monotonic())), delay=5.0)
        q.add(lambda: ran.append(("D-old", clock.monotonic())), delay=3.0, key="renew")
        q.add(lambda: ran.append(("D-new", clock.monotonic())), delay=4.0, key="renew")

        sleeps = 0
        while len(q) > 0:
            wait = q.peek()
            self.assertIsNotNone(wait)
            if wait > 0:
                sleeps += 1
                clock.sleep(wait)
            task = q.pop_ready()
            self.assertIsNotNone(task)
            task()
            if sleeps > 10:
                self.fail("消费循环疑似空转")

        self.assertEqual(ran, [
            ("A", 52.0),
            ("B", 52.0),
            ("D-new", 54.0),
            ("C", 55.0),
        ])
        # 每个到期批次恰好睡一次，不多睡（睡过头）也不少睡（空转）
        self.assertEqual(sleeps, 3)
        self.assertEqual(clock.monotonic(), 55.0)


if __name__ == "__main__":
    unittest.main()
