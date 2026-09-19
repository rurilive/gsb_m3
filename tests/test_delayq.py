"""delayq 防回归测试：覆盖四个线上现象对应的缺陷。"""
import subprocess
import sys
import threading
import unittest
from pathlib import Path

from delayq import DelayedQueue, FakeClock

REPO_ROOT = Path(__file__).resolve().parents[1]


class DelayedQueueTest(unittest.TestCase):

    def setUp(self):
        self.clock = FakeClock(start=100.0)
        self.q = DelayedQueue(clock=self.clock)

    # 现象 1：还没到点的任务不能被捞出来

    def test_not_due_is_not_popped(self):
        fired = []
        self.q.add(lambda: fired.append("late"), delay=10.0)

        self.clock.advance(9.0)
        self.assertIsNone(self.q.pop_ready())
        self.assertEqual(fired, [])
        self.assertEqual(len(self.q), 1)

        self.clock.advance(1.0)
        task = self.q.pop_ready()
        self.assertIsNotNone(task)
        task()
        self.assertEqual(fired, ["late"])
        self.assertEqual(len(self.q), 0)

    def test_zero_and_negative_delay(self):
        fired = []
        self.q.add(lambda: fired.append("now"), delay=0.0)
        self.assertIsNotNone(self.q.pop_ready())
        with self.assertRaises(ValueError):
            self.q.add(lambda: fired.append("bad"), delay=-1.0)

    # 现象 2：同一时刻到期的任务按提交顺序（FIFO）

    def test_same_due_fires_in_submission_order(self):
        order = []
        for name in "ABCDEFGH":
            self.q.add(lambda n=name: order.append(n), delay=3.0)
        self.clock.advance(3.0)
        while True:
            task = self.q.pop_ready()
            if task is None:
                break
            task()
        self.assertEqual(order, list("ABCDEFGH"))

    def test_fifo_across_due_times(self):
        order = []
        self.q.add(lambda: order.append(1), delay=1.0)
        self.q.add(lambda: order.append(2), delay=2.0)
        self.q.add(lambda: order.append(3), delay=2.0)
        self.clock.advance(5.0)
        while True:
            task = self.q.pop_ready()
            if task is None:
                break
            task()
        self.assertEqual(order, [1, 2, 3])

    # 现象 3：同一 key 重复提交只执行最后一次

    def test_duplicate_key_last_submission_wins(self):
        fired = []
        self.q.add(lambda: fired.append("old"), delay=2.0, key="k")
        self.clock.advance(1.0)
        self.q.add(lambda: fired.append("new"), delay=2.0, key="k")
        self.assertEqual(len(self.q), 1)

        self.clock.advance(1.0)
        # 旧条目 due=102 已到期，但必须作废，不能弹出
        self.assertIsNone(self.q.pop_ready())

        self.clock.advance(1.0)
        task = self.q.pop_ready()
        self.assertIsNotNone(task)
        task()
        self.assertEqual(fired, ["new"])
        self.assertIsNone(self.q.pop_ready())

    def test_duplicate_key_stale_entry_skipped_in_peek(self):
        self.q.add(lambda: None, delay=1.0, key="k")
        self.clock.advance(5.0)
        self.q.add(lambda: None, delay=10.0, key="k")
        # 堆顶是早已到期的旧条目，peek 必须跳过它报告新条目
        self.assertAlmostEqual(self.q.peek(), 10.0)

    def test_same_key_resubmitted_after_firing(self):
        fired = []
        self.q.add(lambda: fired.append("first"), delay=1.0, key="k")
        self.clock.advance(1.0)
        self.q.pop_ready()()
        self.q.add(lambda: fired.append("second"), delay=1.0, key="k")
        self.clock.advance(1.0)
        self.q.pop_ready()()
        self.assertEqual(fired, ["first", "second"])

    def test_keyless_entries_never_dedup(self):
        fired = []
        for i in range(3):
            self.q.add(lambda i=i: fired.append(i), delay=1.0)
        self.assertEqual(len(self.q), 3)
        self.clock.advance(1.0)
        count = 0
        while True:
            task = self.q.pop_ready()
            if task is None:
                break
            task()
            count += 1
        self.assertEqual(count, 3)
        self.assertEqual(fired, [0, 1, 2])

    # 现象 4：peek 返回相对等待秒数，不返回绝对时间戳

    def test_peek_returns_remaining_seconds(self):
        self.q.add(lambda: None, delay=5.0)
        self.assertAlmostEqual(self.q.peek(), 5.0)
        self.clock.advance(3.0)
        self.assertAlmostEqual(self.q.peek(), 2.0)
        self.clock.advance(3.0)
        self.assertEqual(self.q.peek(), 0.0)
        self.q.pop_ready()
        self.assertIsNone(self.q.peek())

    def test_peek_points_at_nearest_ready_task(self):
        self.q.add(lambda: None, delay=9.0)
        self.q.add(lambda: None, delay=1.0)
        self.assertAlmostEqual(self.q.peek(), 1.0)

    def test_pop_ready_leaves_future_task_in_heap(self):
        self.q.add(lambda: None, delay=10.0)
        self.clock.advance(1.0)
        self.assertIsNone(self.q.pop_ready())
        self.assertEqual(len(self.q), 1)
        self.q.add(lambda: None, delay=0.0)
        self.assertIsNotNone(self.q.pop_ready())
        self.assertEqual(len(self.q), 1)

    def test_len_excludes_stale_entries(self):
        self.q.add(lambda: None, delay=1.0, key="k")
        self.q.add(lambda: None, delay=1.0, key="k")
        self.q.add(lambda: None, delay=1.0)
        self.assertEqual(len(self.q), 2)

    # 并发冒烟：多线程提交/弹出不报错、不丢任务

    def test_concurrent_add_and_pop(self):
        clock = FakeClock(start=0.0)
        q = DelayedQueue(clock=clock)
        fired = []

        def producer():
            for i in range(200):
                q.add(lambda i=i: fired.append(i), delay=1.0, key=None)

        t = threading.Thread(target=producer)
        t.start()
        t.join()
        clock.advance(1.0)
        while True:
            task = q.pop_ready()
            if task is None:
                break
            task()
        self.assertEqual(len(fired), 200)
        self.assertEqual(len(q), 0)

    def test_concurrent_duplicate_keys(self):
        clock = FakeClock(start=0.0)
        q = DelayedQueue(clock=clock)

        def producer(prefix):
            for i in range(100):
                q.add(lambda: None, delay=1.0, key="shared-%d" % (i % 10))

        threads = [threading.Thread(target=producer, args=(p,)) for p in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(q), 10)
        clock.advance(1.0)
        count = 0
        while q.pop_ready() is not None:
            count += 1
        self.assertEqual(count, 10)


class DemoTest(unittest.TestCase):

    def test_demo_runs_with_correct_timing(self):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "demo.py")],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        task_lines = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("[")]
        # 没有任务提前于 t=102 执行；A/B/D' 在 t=102，C 在 t=105
        self.assertTrue(all("t=102" in ln or "t=105" in ln for ln in task_lines), out)
        joined = "\n".join(task_lines)
        self.assertIn("[A]", joined)
        self.assertIn("[B]", joined)
        self.assertIn("[D']", joined)
        self.assertIn("[C]", joined)
        # 同 key 的旧提交 [D] 不得执行（[D'] 不受影响）
        self.assertNotIn("[D] 会话续期", joined)
        # 同一时刻到期按提交顺序：A < B < D' < C
        names = [ln.split("]")[0] for ln in task_lines]
        self.assertEqual(names, ["[A", "[B", "[D'", "[C"])


if __name__ == "__main__":
    unittest.main()
