"""调用链上下文的锁定测试（确定性，不依赖时序）。"""

import threading
import time
import unittest

from tracectx import (
    TracedThread,
    TracedThreadPoolExecutor,
    async_call,
    current_correlation_id,
    format_report,
    map_batch,
    run_detached,
    span,
    start_trace,
)


class TestCorrelationId(unittest.TestCase):
    def test_no_trace_outside_start_trace(self):
        self.assertIsNone(current_correlation_id())

    def test_id_generated_and_restored(self):
        with start_trace() as cid:
            self.assertEqual(current_correlation_id(), cid)
        self.assertIsNone(current_correlation_id())

    def test_explicit_id_is_used(self):
        with start_trace(correlation_id="fixed-id"):
            self.assertEqual(current_correlation_id(), "fixed-id")

    def test_thread_inherits_current_trace(self):
        box = []
        with start_trace() as cid:
            t = TracedThread(target=lambda: box.append(current_correlation_id()))
            t.start()
            t.join(5)
        self.assertEqual(box, [cid])

    def test_executor_inherits_current_trace(self):
        with start_trace() as cid:
            with TracedThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(current_correlation_id) for _ in range(4)]
                seen = [f.result(5) for f in futures]
        self.assertEqual(seen, [cid] * 4)

    def test_concurrent_traces_do_not_cross(self):
        barrier = threading.Barrier(4, timeout=5)
        seen = {}
        lock = threading.Lock()

        def worker(tag):
            with start_trace() as cid:
                barrier.wait(5)
                time.sleep(0.01)  # 让四条链路充分交叠
                with lock:
                    seen[tag] = (cid, current_correlation_id())

        threads = [TracedThread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(5)

        self.assertEqual(len(seen), 4)
        ids = [cid for cid, _ in seen.values()]
        self.assertEqual(len(set(ids)), 4)  # 各自独立 id
        for cid, now in seen.values():
            self.assertEqual(cid, now)  # 互不串号

    def test_concurrent_submit_no_cross_talk(self):
        barrier = threading.Barrier(2, timeout=5)

        def job():
            with start_trace() as cid:
                barrier.wait(5)
                time.sleep(0.01)
                return cid, current_correlation_id()

        with TracedThreadPoolExecutor(max_workers=2) as pool:
            f1, f2 = pool.submit(job), pool.submit(job)
            r1, r2 = f1.result(5), f2.result(5)
        self.assertNotEqual(r1[0], r2[0])
        self.assertEqual(r1[0], r1[1])
        self.assertEqual(r2[0], r2[1])

    def test_map_batch_carries_trace(self):
        with start_trace() as cid:
            ids = map_batch(lambda _: current_correlation_id(), range(6), workers=3)
        self.assertEqual(set(ids), {cid})

    def test_detached_and_async_carry_trace(self):
        box = []
        done = threading.Event()
        with start_trace() as cid:
            self.assertEqual(run_detached(current_correlation_id), cid)
            t = async_call(
                lambda: (box.append(current_correlation_id()), done.set()))
            self.assertTrue(done.wait(5))
            t.join(5)
        self.assertEqual(box, [cid])


class TestSpanTiming(unittest.TestCase):
    def test_nested_spans_attach_and_time(self):
        with start_trace():
            with span("outer") as outer:
                with span("inner") as inner:
                    pass
        self.assertIs(inner.parent, outer)
        self.assertEqual(outer.children, [inner])
        self.assertIsNotNone(outer.started_at)
        self.assertGreater(inner.duration, 0)
        self.assertGreaterEqual(outer.duration, inner.duration)

    def test_span_without_trace_still_times(self):
        with span("loose") as node:
            pass
        self.assertIsNone(node.parent)
        self.assertGreater(node.duration, 0)

    def test_cross_thread_span_attaches_to_parent(self):
        def work():
            with span("worker"):
                pass

        with start_trace():
            with span("root") as root:
                t = TracedThread(target=work)
                t.start()
                t.join(5)
                with TracedThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(work).result(5)
        self.assertEqual([c.name for c in root.children], ["worker", "worker"])
        for child in root.children:
            self.assertIs(child.parent, root)

    def test_slow_marker_follows_threshold(self):
        with start_trace(slow_threshold=0):
            with span("everything-slow") as slow_one:
                pass
        self.assertTrue(slow_one.slow)

        with start_trace(slow_threshold=3600):
            with span("fast") as fast_one:
                time.sleep(0.005)
        self.assertFalse(fast_one.slow)


class TestReport(unittest.TestCase):
    def test_report_structure(self):
        with start_trace(correlation_id="rid-1", slow_threshold=0):
            with span("root"):
                with span("child"):
                    pass
            report = format_report()

        lines = report.splitlines()
        self.assertIn("rid-1", lines[0])
        root_line = next(l for l in lines if l.strip().startswith("root"))
        child_line = next(l for l in lines if l.strip().startswith("child"))
        self.assertFalse(root_line.startswith(" "))
        self.assertTrue(child_line.startswith("  "))
        self.assertNotEqual(
            lines.index(child_line) - lines.index(root_line), 0)
        for line in (root_line, child_line):
            self.assertIn("ms", line)
            self.assertIn("[SLOW]", line)

    def test_report_marks_only_slow_spans(self):
        with start_trace(slow_threshold=3600):
            with span("calm"):
                pass
            report = format_report()
        self.assertNotIn("[SLOW]", report)
        self.assertIn("calm", report)

    def test_report_requires_active_trace(self):
        with self.assertRaises(RuntimeError):
            format_report()


if __name__ == "__main__":
    unittest.main()
