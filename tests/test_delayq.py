"""delayq 防回归测试：覆盖提前执行、同刻乱序、key 重复、空转/睡过头四类缺陷。"""
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from delayq import DelayedQueue, FakeClock, SystemClock  # noqa: E402


class TestScheduling(unittest.TestCase):

    def test_not_executed_before_due(self):
        # 现象 1：未到点的任务不能被弹出
        clock = FakeClock(start=1000.0)
        q = DelayedQueue(clock=clock)
        q.add(lambda: None, delay=10.0)

        self.assertEqual(len(q), 1)
        clock.advance(9.999)
        self.assertAlmostEqual(q.peek(), 0.001)
        self.assertIsNone(q.pop_ready())

        clock.advance(0.001)
        self.assertEqual(q.peek(), 0.0)
        self.assertIsNotNone(q.pop_ready())  # due <= now 才出队
        self.assertEqual(len(q), 0)
        self.assertIsNone(q.pop_ready())

    def test_due_boundary_is_inclusive(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        q.add(lambda: None, delay=0.0)
        self.assertEqual(q.peek(), 0.0)
        self.assertIsNotNone(q.pop_ready())

    def test_negative_delay_rejected(self):
        q = DelayedQueue(clock=FakeClock())
        with self.assertRaises(ValueError):
            q.add(lambda: None, delay=-0.001)


class TestOrdering(unittest.TestCase):

    def test_same_due_fifo_submission_order(self):
        # 现象 2：同一时刻到期必须先提交先执行，且多次运行结果稳定
        for _ in range(20):
            clock = FakeClock()
            q = DelayedQueue(clock=clock)
            fired = []
            for i in range(50):
                q.add(lambda i=i: fired.append(i), delay=3.0)
            clock.advance(3.0)
            while True:
                task = q.pop_ready()
                if task is None:
                    break
                task()
            self.assertEqual(fired, list(range(50)))

    def test_ordering_across_distinct_due_times(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        fired = []
        q.add(lambda: fired.append("late"), delay=9.0)
        q.add(lambda: fired.append("early"), delay=1.0)
        q.add(lambda: fired.append("mid1"), delay=5.0)
        q.add(lambda: fired.append("mid2"), delay=5.0)
        clock.advance(10.0)
        while True:
            task = q.pop_ready()
            if task is None:
                break
            task()
        self.assertEqual(fired, ["early", "mid1", "mid2", "late"])


class TestKeyDedup(unittest.TestCase):

    def test_duplicate_key_only_latest_runs(self):
        # 现象 3：同 key 重复提交，旧条目到期也不能执行
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        fired = []
        q.add(lambda: fired.append("old"), delay=1.0, key="k")
        q.add(lambda: fired.append("new"), delay=1.0, key="k")
        self.assertEqual(len(q), 1)
        clock.advance(1.0)
        while True:
            task = q.pop_ready()
            if task is None:
                break
            task()
        self.assertEqual(fired, ["new"])
        self.assertEqual(len(q), 0)

    def test_old_entry_due_earlier_than_replacement(self):
        # 旧条目先到期且位于堆顶：peek/pop 都必须跳过它，不能空转
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        fired = []
        q.add(lambda: fired.append("old"), delay=1.0, key="k")
        q.add(lambda: fired.append("new"), delay=10.0, key="k")
        self.assertEqual(len(q), 1)

        self.assertEqual(q.peek(), 10.0)  # 不是 0，消费端不会空转
        clock.advance(1.0)
        self.assertIsNone(q.pop_ready())  # 旧条目到期也不弹
        self.assertEqual(q.peek(), 9.0)

        clock.advance(9.0)
        task = q.pop_ready()
        self.assertIsNotNone(task)
        task()
        self.assertEqual(fired, ["new"])

    def test_replacement_due_earlier_than_old_entry(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        fired = []
        q.add(lambda: fired.append("old"), delay=10.0, key="k")
        q.add(lambda: fired.append("new"), delay=1.0, key="k")

        clock.advance(1.0)
        task = q.pop_ready()
        self.assertIsNotNone(task)
        task()
        self.assertEqual(fired, ["new"])
        self.assertEqual(len(q), 0)

        clock.advance(20.0)
        self.assertIsNone(q.pop_ready())  # 陈旧旧条目被惰性清掉，不执行
        self.assertEqual(fired, ["new"])

    def test_repeated_resubmit(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        fired = []
        for i in range(5):
            q.add(lambda i=i: fired.append(i), delay=1.0, key="k")
        self.assertEqual(len(q), 1)
        clock.advance(1.0)
        task = q.pop_ready()
        self.assertIsNotNone(task)
        task()
        self.assertEqual(fired, [4])

    def test_keyless_entries_never_dedup(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        for _ in range(3):
            q.add(lambda: None, delay=1.0)
        self.assertEqual(len(q), 3)
        clock.advance(1.0)
        count = 0
        while q.pop_ready() is not None:
            count += 1
        self.assertEqual(count, 3)

    def test_distinct_keys_both_run(self):
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        fired = []
        q.add(lambda: fired.append("a"), delay=1.0, key="a")
        q.add(lambda: fired.append("b"), delay=1.0, key="b")
        clock.advance(1.0)
        while True:
            task = q.pop_ready()
            if task is None:
                break
            task()
        self.assertEqual(sorted(fired), ["a", "b"])


class TestPeekAndConsumer(unittest.TestCase):

    def test_peek_empty_returns_none(self):
        q = DelayedQueue(clock=FakeClock())
        self.assertIsNone(q.peek())

    def test_peek_is_relative_remaining_seconds(self):
        # 现象 4：peek 必须是"还要等几秒"，不是绝对到期时刻（否则一口睡过头）
        clock = FakeClock(start=500.0)
        q = DelayedQueue(clock=clock)
        q.add(lambda: None, delay=10.0)
        self.assertEqual(q.peek(), 10.0)
        clock.advance(3.0)
        self.assertEqual(q.peek(), 7.0)
        clock.advance(7.0)
        self.assertEqual(q.peek(), 0.0)  # 已到期夹到 0，不会返回负数

    def test_peek_skips_cancelled_heap_head(self):
        # 现象 4：堆顶是被去重的旧条目时，peek 不能给 0 造成空转
        clock = FakeClock()
        q = DelayedQueue(clock=clock)
        q.add(lambda: None, delay=1.0, key="k")
        q.add(lambda: None, delay=10.0, key="k")
        for _ in range(3):
            clock.advance(0.5)
            self.assertEqual(q.peek(), 10.0 - clock.monotonic())
            self.assertIsNone(q.pop_ready())

    def test_consumer_sleep_peek_loop_no_spin_no_oversleep(self):
        # 模拟消费端：sleep(peek()) 后轮询，验证既不空转也不睡过头
        clock = FakeClock(start=10.0)
        q = DelayedQueue(clock=clock)
        fired_at = []

        def record():
            fired_at.append(clock.monotonic())

        q.add(record, delay=2.0)
        q.add(record, delay=1.0, key="k")
        q.add(record, delay=8.0, key="k")  # 替换掉 1s 的旧条目
        q.add(record, delay=8.0)

        iterations = 0
        while len(q):
            iterations += 1
            self.assertLess(iterations, 100)  # 空转保护：循环次数必须有界
            wait = q.peek()
            self.assertIsNotNone(wait)
            self.assertGreaterEqual(wait, 0.0)
            if wait > 0.0:
                clock.sleep(wait)
            task = q.pop_ready()
            if task is not None:
                task()

        self.assertEqual(fired_at, [12.0, 18.0, 18.0])


class TestThreadSafety(unittest.TestCase):

    def test_concurrent_add_and_consume(self):
        q = DelayedQueue(clock=SystemClock())
        fired = []
        fired_lock = threading.Lock()
        stop = threading.Event()

        def consumer():
            while not stop.is_set():
                wait = q.peek()
                if wait is None:
                    time.sleep(0.001)
                    continue
                time.sleep(min(wait, 0.002))
                task = q.pop_ready()
                if task is not None:
                    with fired_lock:
                        fired.append(task())

        workers = []
        for wid in range(4):
            def produce(wid=wid):
                for i in range(100):
                    q.add(lambda wid=wid, i=i: wid * 1000 + i, 0.0)
                    q.add(lambda i=i: "key-%d" % (i % 10), 0.0,
                          key="key-%d" % (i % 10))
                    time.sleep(0)
            workers.append(threading.Thread(target=produce))
        consumer_thread = threading.Thread(target=consumer)
        all_threads = workers + [consumer_thread]

        for t in all_threads:
            t.start()
        for t in workers:
            t.join()
        deadline = time.time() + 5
        while len(q) > 0 and time.time() < deadline:
            time.sleep(0.002)
        self.assertEqual(len(q), 0)
        stop.set()
        consumer_thread.join()

        # 无 key 的 400 个全部执行；10 个 key 全局只执行一次
        self.assertEqual(len(fired), 410)
        keyed = sorted(x for x in fired if isinstance(x, str))
        self.assertEqual(keyed, ["key-%d" % i for i in range(10)])
        unkeyed = sorted(x for x in fired if isinstance(x, int))
        expected = sorted(wid * 1000 + i for wid in range(4) for i in range(100))
        self.assertEqual(unkeyed, expected)


if __name__ == "__main__":
    unittest.main()
