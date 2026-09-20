"""优雅关闭 close() 的行为测试。

线程节奏全部用 Event 控制，只依赖有限的 wait 超时，不使用 sleep。
"""

import os
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import CancelledError

from workerpool import CANCELLED, FAILED, FINISHED, PoolClosed, WorkerPool

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRejectAfterClose(unittest.TestCase):
    def test_submit_raises_pool_closed(self):
        pool = WorkerPool(2, atexit=False)
        pool.close()
        with self.assertRaises(PoolClosed):
            pool.submit(pow, 2, 3)

    def test_map_raises_pool_closed(self):
        pool = WorkerPool(2, atexit=False)
        pool.close()
        with self.assertRaises(PoolClosed):
            pool.map(str, range(3))

    def test_pool_closed_defined_in_workerpool(self):
        import workerpool
        self.assertIs(workerpool.PoolClosed, PoolClosed)
        from workerpool import pool as pool_mod
        self.assertIs(pool_mod.PoolClosed, PoolClosed)


class TestCloseWaitForever(unittest.TestCase):
    def test_all_running_tasks_settle_without_timeout(self):
        release = threading.Event()
        started = [threading.Event() for _ in range(2)]

        def job(i):
            started[i].set()
            release.wait(5)
            return i

        pool = WorkerPool(2, atexit=False)
        tasks = [pool.submit(job, i) for i in range(2)]
        self.assertTrue(started[0].wait(5))
        self.assertTrue(started[1].wait(5))

        closer = {}

        def do_close():
            closer["report"] = pool.close()

        t = threading.Thread(target=do_close)
        t.start()
        # 无时限等待期间，close 尚未返回
        t.join(0.2)
        self.assertTrue(t.is_alive())
        release.set()
        t.join(5)
        self.assertFalse(t.is_alive())

        report = closer["report"]
        self.assertEqual(report["completed"], 2)
        self.assertEqual(report["cancelled"], [])
        self.assertEqual([task.state for task in tasks], [FINISHED, FINISHED])

    def test_queued_tasks_drain_when_no_timeout(self):
        release = threading.Event()
        started = [threading.Event() for _ in range(3)]

        def job(i):
            started[i].set()
            release.wait(5)
            return i

        pool = WorkerPool(1, atexit=False)
        tasks = [pool.submit(job, i) for i in range(3)]
        self.assertTrue(started[0].wait(5))

        t = threading.Thread(target=pool.close)
        t.start()
        t.join(0.2)
        self.assertTrue(t.is_alive())
        release.set()
        t.join(5)
        self.assertFalse(t.is_alive())

        for i in (1, 2):
            self.assertTrue(started[i].wait(5))
            self.assertEqual(tasks[i].result(5), i)


class TestCloseWithTimeout(unittest.TestCase):
    def test_running_and_queued_marked_cancelled(self):
        release = threading.Event()
        ran = [threading.Event() for _ in range(3)]

        def job(i):
            ran[i].set()
            release.wait(5)
            return i

        pool = WorkerPool(1, atexit=False)
        tasks = [pool.submit(job, i) for i in range(3)]
        self.assertTrue(ran[0].wait(5))

        report = pool.close(grace_timeout=0.1)
        self.assertEqual(report["completed"], 0)
        self.assertEqual(report["cancelled"], tasks)
        for task in tasks:
            self.assertEqual(task.state, CANCELLED)
            self.assertTrue(task.done)
            self.assertTrue(task.cancelled)
            self.assertTrue(task.wait(0))
            with self.assertRaises(CancelledError):
                task.result(0)
            with self.assertRaises(CancelledError):
                task.exception(0)

        # 在途任务 fn 无法撤回，但放开后状态不再翻转
        release.set()
        for worker in pool._workers:
            worker.join(5)
            self.assertFalse(worker.is_alive())
        for task in tasks:
            self.assertEqual(task.state, CANCELLED)

        # 排队任务从未执行
        self.assertFalse(ran[1].is_set())
        self.assertFalse(ran[2].is_set())

    def test_cancelled_in_submission_order(self):
        release = threading.Event()
        started = [threading.Event() for _ in range(2)]

        def blocker(i):
            started[i].set()
            release.wait(5)

        def never():
            pass

        pool = WorkerPool(2, atexit=False)
        blocking = [pool.submit(blocker, i) for i in range(2)]
        queued = [pool.submit(never) for _ in range(3)]
        self.assertTrue(started[0].wait(5))
        self.assertTrue(started[1].wait(5))

        report = pool.close(grace_timeout=0.1)
        self.assertEqual(report["cancelled"], blocking + queued)
        release.set()

    def test_finished_before_deadline_count_completed(self):
        gate = threading.Event()

        def quick():
            return 1

        def slow():
            gate.wait(5)

        pool = WorkerPool(2, atexit=False)
        quick_task = pool.submit(quick)
        slow_task = pool.submit(slow)
        self.assertEqual(quick_task.result(5), 1)

        report = pool.close(grace_timeout=0.1)
        self.assertEqual(report["completed"], 1)
        self.assertEqual(report["cancelled"], [slow_task])
        self.assertEqual(quick_task.state, FINISHED)
        self.assertEqual(slow_task.state, CANCELLED)
        gate.set()

    def test_task_finishing_within_grace_period_completes(self):
        gate = threading.Event()
        started = threading.Event()

        def job():
            started.set()
            gate.wait(5)
            return "done"

        pool = WorkerPool(1, atexit=False)
        task = pool.submit(job)
        self.assertTrue(started.wait(5))

        def release_soon():
            gate.set()

        threading.Timer(0.1, release_soon).start()
        report = pool.close(grace_timeout=5)
        self.assertEqual(report["completed"], 1)
        self.assertEqual(report["cancelled"], [])
        self.assertEqual(task.result(5), "done")

    def test_failed_tasks_count_as_completed(self):
        gate = threading.Event()

        def bad():
            raise ValueError("boom")

        def slow():
            gate.wait(5)

        pool = WorkerPool(2, atexit=False)
        bad_task = pool.submit(bad)
        slow_task = pool.submit(slow)
        self.assertIsInstance(bad_task.exception(5), ValueError)

        report = pool.close(grace_timeout=0.1)
        self.assertEqual(report["completed"], 1)
        self.assertEqual(report["cancelled"], [slow_task])
        self.assertEqual(bad_task.state, FAILED)
        self.assertEqual(slow_task.state, CANCELLED)
        gate.set()

    def test_state_never_flips_after_cancel(self):
        release = threading.Event()

        def slow():
            release.wait(5)
            return "late"

        pool = WorkerPool(1, atexit=False)
        task = pool.submit(slow)
        pool.close(grace_timeout=0.1)
        self.assertEqual(task.state, CANCELLED)
        release.set()
        for worker in pool._workers:
            worker.join(5)
        self.assertEqual(task.state, CANCELLED)
        self.assertTrue(task.cancelled)


class TestCloseIdempotent(unittest.TestCase):
    def test_repeat_close_returns_first_report(self):
        pool = WorkerPool(2, atexit=False)
        tasks = [pool.submit(str, i) for i in range(3)]
        first = pool.close(grace_timeout=5)
        second = pool.close()
        third = pool.close(grace_timeout=0.01)
        self.assertIs(first, second)
        self.assertIs(first, third)
        self.assertEqual(first["completed"], 3)
        self.assertEqual(first["cancelled"], [])
        self.assertEqual([t.state for t in tasks], [FINISHED] * 3)

    def test_concurrent_closes_share_one_report(self):
        release = threading.Event()

        def job():
            release.wait(5)

        pool = WorkerPool(1, atexit=False)
        pool.submit(job)
        reports = []

        def do_close():
            reports.append(pool.close(grace_timeout=0.1))

        threads = [threading.Thread(target=do_close) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(5)
        self.assertTrue(reports)
        self.assertTrue(all(r is reports[0] for r in reports))
        release.set()


class TestCloseEmpty(unittest.TestCase):
    def test_close_without_tasks(self):
        pool = WorkerPool(2, atexit=False)
        report = pool.close()
        self.assertEqual(report, {"completed": 0, "cancelled": []})


class TestAtexit(unittest.TestCase):
    @staticmethod
    def _run_child(source):
        fd, path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd, "w") as f:
                f.write("import sys\n")
                f.write(f"sys.path.insert(0, {REPO_ROOT!r})\n")
                f.write(source)
            proc = subprocess.run(
                [sys.executable, path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )
            return proc
        finally:
            os.unlink(path)

    def test_atexit_registered_flag(self):
        pool = WorkerPool(1)
        try:
            self.assertTrue(pool.atexit_registered)
        finally:
            pool.close()
        pool_no_atexit = WorkerPool(1, atexit=False)
        self.assertFalse(pool_no_atexit.atexit_registered)
        pool_no_atexit.close()

    def test_atexit_waits_for_inflight_tasks(self):
        marker = tempfile.mktemp()
        source = (
            "import threading\n"
            "from workerpool import WorkerPool\n"
            "ready = threading.Event()\n"
            "def job():\n"
            "    ready.set()\n"
            "    threading.Event().wait(0.3)\n"
            f"    open({marker!r}, 'w').write('finished')\n"
            "pool = WorkerPool(1)\n"
            "pool.submit(job)\n"
            "assert ready.wait(5)\n"
        )
        proc = self._run_child(source)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        with open(marker) as f:
            self.assertEqual(f.read(), "finished")
        os.unlink(marker)

    def test_disabling_atexit_exits_without_waiting(self):
        source = (
            "import threading\n"
            "from workerpool import WorkerPool\n"
            "block = threading.Event()\n"
            "pool = WorkerPool(1, atexit=False)\n"
            "pool.submit(block.wait)\n"
            "threading.Event().wait(0.2)\n"
        )
        proc = self._run_child(source)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())


if __name__ == "__main__":
    unittest.main()
