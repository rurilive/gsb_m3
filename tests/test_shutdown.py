"""优雅关闭行为的测试。

与 test_pool.py 同一套节奏控制：全部用 Event 同步，等待只依赖
有限的 wait 超时，不使用 sleep，任何环境下结果一致。
"""

import os
import subprocess
import sys
import threading
import unittest

from workerpool import PoolClosed, WorkerPool
from workerpool.pool import CANCELLED, FINISHED

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCloseRejectsNewWork(unittest.TestCase):
    def test_submit_raises_pool_closed_after_close(self):
        pool = WorkerPool(1)
        pool.close()
        with self.assertRaises(PoolClosed):
            pool.submit(str, 1)

    def test_map_rejected_after_close(self):
        pool = WorkerPool(1)
        pool.close()
        with self.assertRaises(PoolClosed):
            pool.map(str, [1, 2, 3])

    def test_close_on_idle_pool(self):
        pool = WorkerPool(2)
        report = pool.close()
        self.assertEqual(report.completed, 0)
        self.assertEqual(report.cancelled, [])


class TestGracefulClose(unittest.TestCase):
    def test_close_without_timeout_waits_for_all(self):
        gate = threading.Event()
        started = threading.Event()

        def job(i):
            started.set()
            gate.wait(5)
            return i

        pool = WorkerPool(1)
        t0 = pool.submit(job, 0)
        t1 = pool.submit(job, 1)
        # t0 在跑、t1 排队时开始关闭
        self.assertTrue(started.wait(5))
        outcome = {}
        closer = threading.Thread(
            target=lambda: outcome.setdefault("report", pool.close()), daemon=True
        )
        closer.start()
        # gate 未放开，无时限的 close 必须一直等
        closer.join(0.2)
        self.assertTrue(closer.is_alive())
        gate.set()
        closer.join(5)
        self.assertFalse(closer.is_alive())
        report = outcome["report"]
        self.assertEqual(report.completed, 2)
        self.assertEqual(report.cancelled, [])
        self.assertEqual(t0.state, FINISHED)
        self.assertEqual(t1.state, FINISHED)
        self.assertEqual(t0.result(5), 0)
        self.assertEqual(t1.result(5), 1)

    def test_close_with_timeout_cancels_unsettled(self):
        gate = threading.Event()
        running_started = threading.Event()
        running_returned = threading.Event()
        queued_ran = threading.Event()

        def blocking():
            running_started.set()
            gate.wait(5)
            running_returned.set()

        def queued():
            queued_ran.set()

        pool = WorkerPool(1)
        t0 = pool.submit(blocking)
        t1 = pool.submit(queued)
        self.assertTrue(running_started.wait(5))
        report = pool.close(grace_timeout=0.2)
        # 在跑的和排队的都没落定，全部被取消
        self.assertEqual(report.completed, 0)
        self.assertEqual(report.cancelled, [t0, t1])
        self.assertEqual(t0.state, CANCELLED)
        self.assertEqual(t1.state, CANCELLED)
        self.assertTrue(t0.done)
        self.assertTrue(t1.done)
        # 取消后状态不再翻转：放行在跑任务，落定后仍是 cancelled
        gate.set()
        self.assertTrue(running_returned.wait(5))
        # 排队中的取消任务不再被执行
        self.assertFalse(queued_ran.wait(0.2))
        self.assertEqual(t0.state, CANCELLED)
        self.assertEqual(t1.state, CANCELLED)

    def test_completed_counts_only_settled_during_close(self):
        gate = threading.Event()
        started = threading.Event()

        def blocking():
            started.set()
            gate.wait(5)

        pool = WorkerPool(2)
        quick = pool.submit(str, 1)
        self.assertEqual(quick.result(5), "1")
        slow = pool.submit(blocking)
        self.assertTrue(started.wait(5))
        report = pool.close(grace_timeout=0.2)
        gate.set()
        # quick 在 close 前已落定，不计入“本次落定”
        self.assertEqual(report.completed, 0)
        self.assertEqual(report.cancelled, [slow])

    def test_settled_before_deadline_are_completed(self):
        gate = threading.Event()
        entered = threading.Event()

        def job():
            entered.set()
            gate.wait(5)
            return "ok"

        pool = WorkerPool(1)
        t = pool.submit(job)
        self.assertTrue(entered.wait(5))
        outcome = {}
        closer = threading.Thread(
            target=lambda: outcome.setdefault("report", pool.close(grace_timeout=5)),
            daemon=True,
        )
        closer.start()
        # 时限还早，close 在等任务落定
        closer.join(0.2)
        self.assertTrue(closer.is_alive())
        gate.set()
        closer.join(5)
        report = outcome["report"]
        self.assertEqual(report.completed, 1)
        self.assertEqual(report.cancelled, [])
        self.assertEqual(t.state, FINISHED)

    def test_repeated_close_is_idempotent(self):
        pool = WorkerPool(1)
        pool.submit(str, 1)
        first = pool.close()
        self.assertEqual(first.completed, 1)
        self.assertIs(pool.close(), first)
        self.assertIs(pool.close(grace_timeout=0.1), first)


class TestAtexit(unittest.TestCase):
    def test_atexit_registered_flag(self):
        self.assertTrue(WorkerPool(1, atexit=True).atexit_registered)
        self.assertFalse(WorkerPool(1, atexit=False).atexit_registered)
        # 默认注册
        self.assertTrue(WorkerPool(1).atexit_registered)

    def test_atexit_settles_tasks_at_exit(self):
        code = (
            "import threading\n"
            "from workerpool import WorkerPool\n"
            "gate = threading.Event()\n"
            "def job():\n"
            "    gate.wait(5)\n"
            "    print('job-done', flush=True)\n"
            "pool = WorkerPool(1)\n"
            "pool.submit(job)\n"
            "gate.set()\n"
            "# 不显式 close：进程退出靠 atexit 按 close 语义收尾\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("job-done", proc.stdout)


if __name__ == "__main__":
    unittest.main()
