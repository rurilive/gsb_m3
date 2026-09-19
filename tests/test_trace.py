"""跨线程调用链上下文：并发隔离、嵌套计时、树形报告结构。"""

import re
import threading
import time
import unittest

from tracectx import (
    TracedThreadPoolExecutor,
    TracedThread,
    async_call,
    current_cid,
    current_span,
    format_tree,
    map_batch,
    new_cid,
    run_detached,
    span,
    trace_session,
)


class TestCorrelationId(unittest.TestCase):
    def test_new_cid_format_and_uniqueness(self):
        ids = {new_cid() for _ in range(100)}
        self.assertEqual(len(ids), 100)
        for cid in ids:
            self.assertTrue(cid.startswith("cid-"))
            self.assertRegex(cid, r"^cid-[0-9a-f]{12}$")

    def test_no_cid_outside_session(self):
        self.assertIsNone(current_cid())
        self.assertIsNone(current_span())

    def test_session_sets_and_restores_cid(self):
        self.assertIsNone(current_cid())
        with trace_session("root", cid="cid-fixed") as sess:
            self.assertEqual(sess.cid, "cid-fixed")
            self.assertEqual(current_cid(), "cid-fixed")
        self.assertIsNone(current_cid())

    def test_traced_thread_propagates_cid(self):
        seen = []
        done = threading.Event()

        def work():
            seen.append(current_cid())
            done.set()

        with trace_session("root", cid="cid-t1"):
            t = TracedThread(target=work)
            t.start()
            t.join(5)
        self.assertTrue(done.wait(5))
        self.assertEqual(seen, ["cid-t1"])

    def test_thread_context_change_does_not_leak_back(self):
        def work():
            # 工作线程内即便再起一段上下文，也不影响提交方
            with trace_session("inner", cid="cid-inner"):
                self.assertEqual(current_cid(), "cid-inner")

        with trace_session("root", cid="cid-outer"):
            t = TracedThread(target=work)
            t.start()
            t.join(5)
            self.assertEqual(current_cid(), "cid-outer")

    def test_concurrent_sessions_do_not_crosstalk(self):
        records = []
        lock = threading.Lock()
        n_workers = 4
        barrier = threading.Barrier(n_workers * 2, timeout=5)

        def work(cid, root):
            barrier.wait()
            with span("child"):
                with lock:
                    records.append((current_cid(), current_span()))
                time.sleep(0.01)

        def drive(cid, roots):
            with trace_session("sess", cid=cid, slow_threshold=100) as sess:
                roots[cid] = sess.root
                threads = [TracedThread(target=work, args=(cid, sess.root))
                           for _ in range(n_workers)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(5)

        roots = {}
        drivers = [threading.Thread(target=drive, args=(cid, roots))
                   for cid in ("cid-aaa", "cid-bbb")]
        for t in drivers:
            t.start()
        for t in drivers:
            t.join(5)

        self.assertEqual(len(records), n_workers * 2)
        for cid, sp in records:
            self.assertEqual(cid, sp.cid)
            self.assertIn(cid, ("cid-aaa", "cid-bbb"))
            self.assertIs(sp.parent, roots[cid])
        for root in roots.values():
            self.assertEqual(len(root.children), n_workers)
        self.assertIsNone(current_cid())

    def test_thread_pool_propagates_and_isolates_cid(self):
        pool = TracedThreadPoolExecutor(max_workers=8)
        barrier = threading.Barrier(6, timeout=5)

        def work(expected):
            barrier.wait()
            with span("pool-child") as child:
                time.sleep(0.01)
            return current_cid(), child

        def drive(cid, box):
            with trace_session("pool-sess", cid=cid, slow_threshold=100) as sess:
                futures = [pool.submit(work, cid) for _ in range(3)]
                box["root"] = sess.root
                box["res"] = [f.result(5) for f in futures]

        boxes = {}
        drivers = [threading.Thread(target=drive, args=(cid, boxes.setdefault(cid, {})))
                   for cid in ("cid-p1", "cid-p2")]
        for t in drivers:
            t.start()
        for t in drivers:
            t.join(5)
        pool.shutdown()

        for cid, box in boxes.items():
            self.assertEqual(len(box["res"]), 3)
            for seen_cid, sp in box["res"]:
                self.assertEqual(seen_cid, cid)
                self.assertEqual(sp.cid, cid)
                self.assertIs(sp.parent, box["root"])
            self.assertEqual(len(box["root"].children), 3)

    def test_execution_layer_propagates_cid(self):
        with trace_session("root", cid="cid-exec", slow_threshold=100) as sess:
            def fn(item):
                return (current_cid(), current_span())

            results = map_batch(fn, [1, 2, 3], workers=3)
            for cid, sp in results:
                self.assertEqual(cid, "cid-exec")
                self.assertIs(sp, sess.root)

            self.assertEqual(run_detached(current_cid), "cid-exec")

            done = threading.Event()
            box = {}
            async_call(current_cid,
                       on_done=lambda v: (box.__setitem__("cid", v), done.set()))
            self.assertTrue(done.wait(5))
            self.assertEqual(box["cid"], "cid-exec")


class TestNestedTiming(unittest.TestCase):
    def test_nested_spans_levels_and_ordering(self):
        with trace_session("root", cid="cid-n", slow_threshold=100) as sess:
            time.sleep(0.01)
            with span("a") as a:
                time.sleep(0.02)
                with span("b") as b:
                    time.sleep(0.02)

        root = sess.root
        self.assertEqual(root.level, 0)
        self.assertEqual(a.level, 1)
        self.assertEqual(b.level, 2)
        self.assertIs(a.parent, root)
        self.assertIs(b.parent, a)
        self.assertEqual(root.snapshot_children(), [a])
        self.assertEqual(a.snapshot_children(), [b])
        self.assertGreater(b.elapsed, 0.0)
        self.assertGreaterEqual(a.elapsed, b.elapsed - 0.5)
        self.assertGreaterEqual(root.elapsed, a.elapsed - 0.5)
        self.assertGreaterEqual(root.elapsed, 0.04)

    def test_span_in_worker_thread_attaches_under_current_span(self):
        with trace_session("root", cid="cid-cross", slow_threshold=100) as sess:
            def work():
                with span("worker"):
                    time.sleep(0.01)

            t = TracedThread(target=work)
            t.start()
            t.join(5)

        children = sess.root.snapshot_children()
        self.assertEqual([c.name for c in children], ["worker"])
        self.assertEqual(children[0].level, 1)
        self.assertIs(children[0].parent, sess.root)
        self.assertEqual(children[0].cid, "cid-cross")

    def test_many_threads_attach_siblings_concurrently(self):
        n = 20
        with trace_session("root", slow_threshold=100) as sess:
            def work(i):
                with span("w%d" % i):
                    time.sleep(0.002)

            threads = [TracedThread(target=work, args=(i,)) for i in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(5)

        self.assertEqual(len(sess.root.children), n)
        self.assertEqual({c.name for c in sess.root.children},
                         {"w%d" % i for i in range(n)})
        for child in sess.root.children:
            self.assertIs(child.parent, sess.root)

    def test_span_closes_on_exception_and_context_resets(self):
        with trace_session("root", cid="cid-err", slow_threshold=100) as sess:
            with self.assertRaises(RuntimeError):
                with span("boom") as sp:
                    raise RuntimeError("x")
            self.assertIsNotNone(sp.end)
            self.assertIs(current_span(), sess.root)
        self.assertIsNone(current_span())
        self.assertIsNone(current_cid())

    def test_slow_threshold_marks_slow_span(self):
        with trace_session("root", slow_threshold=100) as sess:
            with span("fast") as fast:
                pass
            with span("slow-one", slow_threshold=0.001) as slow_one:
                time.sleep(0.02)
            with span("disabled", slow_threshold=float("inf")) as disabled:
                time.sleep(0.01)

        self.assertFalse(fast.slow)
        self.assertTrue(slow_one.slow)
        self.assertFalse(disabled.slow)
        self.assertFalse(sess.root.slow)

    def test_child_inherits_session_threshold(self):
        with trace_session("root", slow_threshold=0.001) as sess:
            with span("child") as child:
                time.sleep(0.02)
        self.assertTrue(child.slow)
        self.assertTrue(sess.root.slow)


class TestTreeReport(unittest.TestCase):
    def test_report_indentation_names_units_and_slow_marker(self):
        with trace_session("root", slow_threshold=100) as sess:
            with span("fast-step"):
                pass
            with span("slow-step", slow_threshold=0.001):
                time.sleep(0.02)
                with span("inner-step", slow_threshold=100):
                    time.sleep(0.01)

        report = sess.root.to_tree()
        lines = report.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertRegex(lines[0], r"^root  \d+\.\d{3}ms$")
        self.assertRegex(lines[1], r"^  fast-step  \d+\.\d{3}ms$")
        self.assertRegex(lines[2], r"^  slow-step  \d+\.\d{3}ms  \[slow\]$")
        self.assertRegex(lines[3], r"^    inner-step  \d+\.\d{3}ms$")

    def test_format_tree_function_equals_span_method(self):
        with trace_session("root", slow_threshold=100) as sess:
            with span("a"):
                pass
        self.assertEqual(format_tree(sess.root), sess.root.to_tree())

    def test_report_each_line_has_name_and_duration(self):
        with trace_session("demo", slow_threshold=0.001) as sess:
            with span("one"):
                time.sleep(0.02)

        for line in sess.root.to_tree().splitlines():
            self.assertRegex(line, r"^\s*\S+  \d+\.\d{3}(ms|s)(  \[slow\])?$")
            self.assertNotIn("None", line)


if __name__ == "__main__":
    unittest.main()
