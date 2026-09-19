"""delayq 防回归测试：覆盖四个线上现象的根因。"""
import unittest

from delayq import DelayedQueue, FakeClock


def make_task(log, name):
    return lambda: log.append(name)


class PopReadyMaturityTest(unittest.TestCase):
    """现象 1：还没到点的任务被提前捞出执行。"""

    def test_not_due_task_is_not_popped(self):
        clock = FakeClock(start=0.0)
        q = DelayedQueue(clock=clock)
        log = []
        q.add(make_task(log, "A"), delay=5.0)

        clock.advance(4.0)
        self.assertIsNone(q.pop_ready())
        self.assertEqual(log, [])
        self.assertEqual(len(q), 1)

        clock.advance(1.0)
        self.assertIsNotNone(q.pop_ready())
        self.assertEqual(len(q), 0)

    def test_due_boundary_is_ready(self):
        clock = FakeClock(start=10.0)
        q = DelayedQueue(clock=clock)
        q.add(make_task([], "A"), delay=3.0)
        clock.jump_to(12.999)
        self.assertIsNone(q.pop_ready())
        clock.jump_to(13.0)
        self.assertIsNotNone(q.pop_ready())


class FifoOrderTest(unittest.TestCase):
    """现象 2：同一时刻到期的任务须按提交顺序出队。"""

    def test_same_due_pops_in_submission_order(self):
        clock = FakeClock(start=0.0)
        q = DelayedQueue(clock=clock)
        log = []
        for name in ["A", "B", "C", "D", "E"]:
            q.add(make_task(log, name), delay=2.0)
        clock.advance(2.0)
        while True:
            task = q.pop_ready()
            if task is None:
                break
            task()
        self.assertEqual(log, ["A", "B", "C", "D", "E"])

    def test_mixed_delays_pop_by_due_then_fifo(self):
        clock = FakeClock(start=0.0)
        q = DelayedQueue(clock=clock)
        log = []
        q.add(make_task(log, "late"), delay=5.0)
        q.add(make_task(log, "first"), delay=1.0)
        q.add(make_task(log, "second"), delay=1.0)
        clock.advance(5.0)
        while True:
            task = q.pop_ready()
            if task is None:
                break
            task()
        self.assertEqual(log, ["first", "second", "late"])


class KeyDedupTest(unittest.TestCase):
    """现象 3：同 key 重复提交以最后一次为准，旧条目作废。"""

    def test_stale_entry_is_not_executed(self):
        clock = FakeClock(start=0.0)
        q = DelayedQueue(clock=clock)
        log = []
        q.add(make_task(log, "old"), delay=2.0, key="renew")
        q.add(make_task(log, "new"), delay=2.0, key="renew")

        self.assertEqual(len(q), 1)
        clock.advance(2.0)
        task = q.pop_ready()
        self.assertIsNotNone(task)
        task()
        self.assertEqual(log, ["new"])
        self.assertIsNone(q.pop_ready())
        self.assertEqual(len(q), 0)

    def test_resubmit_extends_due(self):
        clock = FakeClock(start=0.0)
        q = DelayedQueue(clock=clock)
        log = []
        q.add(make_task(log, "old"), delay=2.0, key="k")
        clock.advance(1.0)
        q.add(make_task(log, "new"), delay=2.0, key="k")

        clock.advance(1.0)  # t=2：旧条目原本到期，但已作废
        self.assertIsNone(q.pop_ready())
        clock.advance(1.0)  # t=3：新条目到期
        task = q.pop_ready()
        self.assertIsNotNone(task)
        task()
        self.assertEqual(log, ["new"])

    def test_key_can_be_reused_after_pop(self):
        clock = FakeClock(start=0.0)
        q = DelayedQueue(clock=clock)
        log = []
        q.add(make_task(log, "run1"), delay=1.0, key="k")
        clock.advance(1.0)
        q.pop_ready()()
        q.add(make_task(log, "run2"), delay=1.0, key="k")
        clock.advance(1.0)
        q.pop_ready()()
        self.assertEqual(log, ["run1", "run2"])


class PeekSemanticsTest(unittest.TestCase):
    """现象 4：peek 返回剩余等待秒数，消费端按它睡眠不空转、不睡过头。"""

    def test_peek_returns_remaining_wait_not_absolute_due(self):
        clock = FakeClock(start=100.0)
        q = DelayedQueue(clock=clock)
        q.add(make_task([], "A"), delay=5.0)
        self.assertEqual(q.peek(), 5.0)
        clock.advance(2.0)
        self.assertEqual(q.peek(), 3.0)

    def test_peek_clamps_to_zero_when_overdue(self):
        clock = FakeClock(start=0.0)
        q = DelayedQueue(clock=clock)
        q.add(make_task([], "A"), delay=1.0)
        clock.advance(2.0)
        self.assertEqual(q.peek(), 0.0)

    def test_peek_empty_queue_returns_none(self):
        q = DelayedQueue(clock=FakeClock())
        self.assertIsNone(q.peek())

    def test_peek_ignores_cancelled_entries(self):
        clock = FakeClock(start=0.0)
        q = DelayedQueue(clock=clock)
        q.add(make_task([], "old"), delay=1.0, key="k")
        q.add(make_task([], "new"), delay=10.0, key="k")
        self.assertEqual(q.peek(), 10.0)

    def test_sleep_poll_loop_never_oversleeps(self):
        # 模拟消费端：按 peek 睡眠后轮询，任务应在到期时刻准点执行
        clock = FakeClock(start=0.0)
        q = DelayedQueue(clock=clock)
        ran_at = []
        q.add(lambda: ran_at.append(clock.monotonic()), delay=3.0)
        for _ in range(10):
            wait = q.peek()
            if wait is None:
                break
            clock.sleep(wait)
            while True:
                task = q.pop_ready()
                if task is None:
                    break
                task()
        self.assertEqual(ran_at, [3.0])


class ValidationTest(unittest.TestCase):

    def test_negative_delay_rejected(self):
        q = DelayedQueue(clock=FakeClock())
        with self.assertRaises(ValueError):
            q.add(make_task([], "A"), delay=-0.1)


if __name__ == "__main__":
    unittest.main()
