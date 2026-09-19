"""结构化日志层测试。

覆盖：sink 捕获、级别过滤、线程上下文隔离（threading.local）、
文件按大小轮转，以及兼容模式（plain）与结构化渲染。
"""

import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stdout

from loglite.logging import (
    DEBUG,
    WARNING,
    CaptureSink,
    FileSink,
    StreamSink,
    add_sink,
    clear_context,
    clear_sinks,
    get_context,
    get_logger,
    remove_sink,
    render_json,
    render_plain,
    reset,
    set_context,
    set_level,
)
from loglite.logging import Record


class LoggingTestBase(unittest.TestCase):
    def setUp(self):
        reset()
        clear_sinks()  # 默认 stdout sink 不参与本文件的断言，避免污染测试输出

    def tearDown(self):
        reset()


class TestCaptureAndLevels(LoggingTestBase):
    def test_capture_collects_records_and_lines(self):
        sink = CaptureSink()
        add_sink(sink)
        log = get_logger("capa")
        log.info("hello")
        log.warning("oops")
        self.assertEqual(len(sink.records), 2)
        self.assertEqual([r.levelname for r in sink.records], ["INFO", "WARNING"])
        self.assertEqual(
            [r.message for r in sink.records], ["[capa] hello", "[capa] oops"]
        )
        head = sink.lines[0].split(" ", 3)
        self.assertEqual(head[1:3], ["INFO", "capa"])
        self.assertTrue(head[3].endswith("[capa] hello"))

    def test_below_global_level_not_emitted(self):
        sink = CaptureSink()
        add_sink(sink)
        log = get_logger("lvla")
        set_level(WARNING)
        log.debug("d")
        log.info("i")
        log.warning("w")
        log.error("e")
        self.assertEqual([r.message for r in sink.records], ["[lvla] w", "[lvla] e"])

    def test_set_level_by_name_and_int(self):
        sink = CaptureSink()
        add_sink(sink)
        log = get_logger("lvlb")
        set_level("ERROR")
        log.warning("hidden")
        log.error("shown")
        self.assertEqual([r.message for r in sink.records], ["[lvlb] shown"])
        set_level(DEBUG)
        log.debug("now shown")
        self.assertEqual(len(sink.records), 2)

    def test_filtered_records_reach_no_sink(self):
        first = CaptureSink()
        second = CaptureSink()
        add_sink(first, second)
        set_level("INFO")
        get_logger("lvlc").debug("nobody gets this")
        self.assertEqual(first.records, [])
        self.assertEqual(second.records, [])

    def test_remove_sink(self):
        sink = CaptureSink()
        add_sink(sink)
        get_logger("lvld").info("one")
        remove_sink(sink)
        get_logger("lvld").info("two")
        self.assertEqual([r.message for r in sink.records], ["[lvld] one"])

    def test_unknown_level_raises(self):
        with self.assertRaises(ValueError):
            set_level("TRACE")


class TestContext(LoggingTestBase):
    def test_context_attached_to_every_record(self):
        sink = CaptureSink()
        add_sink(sink)
        log = get_logger("ctxa")
        set_context(job="scan", run_id=7)
        log.info("m1")
        log.info("m2")
        for record in sink.records:
            self.assertEqual(record.context, {"job": "scan", "run_id": 7})
        self.assertTrue(sink.lines[0].endswith("[job=scan run_id=7]"))

    def test_context_update_and_clear(self):
        sink = CaptureSink()
        add_sink(sink)
        log = get_logger("ctxb")
        set_context(a=1)
        log.info("first")
        set_context(b=2)  # 合并：a 保留
        log.info("second")
        self.assertEqual(sink.records[0].context, {"a": 1})
        self.assertEqual(sink.records[1].context, {"a": 1, "b": 2})
        clear_context()
        self.assertEqual(get_context(), {})
        log.info("third")
        self.assertEqual(sink.records[2].context, {})
        self.assertNotIn("a=1", sink.lines[2])
        self.assertTrue(sink.lines[2].rstrip().endswith("[ctxb] third"))


class TestThreadContextIsolation(LoggingTestBase):
    def test_thread_contexts_do_not_leak(self):
        sink = CaptureSink()
        add_sink(sink)

        t1_ready = threading.Event()
        t2_ready = threading.Event()
        t1_logged = threading.Event()
        all_logged = threading.Event()
        errors = []

        def worker_one():
            try:
                set_context(worker="t1", shard="alpha")
                log = get_logger("iso")
                t1_ready.set()
                t2_ready.wait(timeout=5)       # 等 t2 也设好自己的上下文
                t1_logged.wait(timeout=5)      # 等 t2 先记日志
                log.info("from-t1")            # t1 上下文不应被 t2 污染
            except Exception as exc:  # pragma: no cover - 失败路径
                errors.append(exc)

        def worker_two():
            try:
                set_context(worker="t2", shard="beta")
                log = get_logger("iso")
                t1_ready.wait(timeout=5)       # 等 t1 上下文就位
                t2_ready.set()
                log.info("from-t2")
                t1_logged.set()
                all_logged.wait(timeout=5)
                log.info("t2-again")           # t1 后续动作不影响 t2
            except Exception as exc:  # pragma: no cover - 失败路径
                errors.append(exc)

        t1 = threading.Thread(target=worker_one)
        t2 = threading.Thread(target=worker_two)
        t1.start()
        t2.start()
        self.assertTrue(t1.join(timeout=5) is None)
        all_logged.set()
        t2.join(timeout=5)
        self.assertFalse(t1.is_alive() or t2.is_alive())
        self.assertEqual(errors, [])

        by_msg = {record.message: record for record in sink.records}
        self.assertEqual(
            by_msg["[iso] from-t2"].context, {"worker": "t2", "shard": "beta"}
        )
        self.assertEqual(
            by_msg["[iso] from-t1"].context, {"worker": "t1", "shard": "alpha"}
        )
        self.assertEqual(
            by_msg["[iso] t2-again"].context, {"worker": "t2", "shard": "beta"}
        )

    def test_main_context_invisible_to_child_thread(self):
        sink = CaptureSink()
        add_sink(sink)
        set_context(worker="main")
        seen = {}
        done = threading.Event()

        def child():
            seen["ctx"] = dict(get_context())
            get_logger("iso2").info("child")
            done.set()

        thread = threading.Thread(target=child)
        thread.start()
        self.assertTrue(done.wait(timeout=5))
        thread.join(timeout=5)
        self.assertEqual(seen["ctx"], {})
        self.assertEqual(sink.records[0].context, {})
        self.assertEqual(get_context(), {"worker": "main"})  # 子线程不反向污染主线程

    def test_clear_context_is_thread_local(self):
        sink = CaptureSink()
        add_sink(sink)

        t1_set = threading.Event()
        t2_cleared = threading.Event()

        def worker_one():
            set_context(worker="t1")
            t1_set.set()
            t2_cleared.wait(timeout=5)
            get_logger("iso3").info("t1-keeps")

        def worker_two():
            set_context(worker="t2")
            t1_set.wait(timeout=5)
            clear_context()
            t2_cleared.set()
            get_logger("iso3").info("t2-cleared")

        t1 = threading.Thread(target=worker_one)
        t2 = threading.Thread(target=worker_two)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        by_msg = {record.message: record for record in sink.records}
        self.assertEqual(by_msg["[iso3] t1-keeps"].context, {"worker": "t1"})
        self.assertEqual(by_msg["[iso3] t2-cleared"].context, {})


class TestRenderers(LoggingTestBase):
    def test_plain_renderer_has_no_decoration(self):
        record = Record(WARNING, "plainx", "[plainx] msg", {"k": "v"}, created=0.0)
        self.assertEqual(render_plain(record), "[plainx] msg")
        payload = json.loads(render_json(record))
        self.assertEqual(payload["level"], "WARNING")
        self.assertEqual(payload["k"], "v")
        self.assertEqual(payload["msg"], "[plainx] msg")

    def test_compat_stdout_matches_legacy_print(self):
        add_sink(StreamSink())
        buf = io.StringIO()
        with redirect_stdout(buf):
            get_logger("legacy").info("start: 1 entries")
        self.assertEqual(buf.getvalue(), "[legacy] start: 1 entries\n")

    def test_stream_sink_supports_text_render(self):
        buf = io.StringIO()
        sink = StreamSink(buf, render="text")
        add_sink(sink)
        set_context(job="demo")
        get_logger("strm").warning("careful")
        line = buf.getvalue().rstrip("\n")
        self.assertIn("WARNING", line)
        self.assertIn("[strm] careful", line)
        self.assertTrue(line.endswith("[job=demo]"))


class TestFileRotation(LoggingTestBase):
    def _read(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_rotation_shifts_and_caps_backups(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "scan.log")
        # 空前缀的 logger，plain 渲染每行恰为 "Lxx\n"（4 字节）；
        # max_bytes=12 时每个文件恰好容纳 3 行。
        log = get_logger("rot", prefix="")
        with FileSink(path, max_bytes=12, backups=2, render="plain") as fsink:
            add_sink(fsink)
            for idx in range(1, 11):
                log.info(f"L{idx:02d}")

        current = self._read(path)
        one = self._read(path + ".1")
        two = self._read(path + ".2")
        # 分组：1-3 / 4-6 / 7-9 / 10；backups=2 时最旧的 1-3 已被删除，
        # .2 最旧、.1 最新。
        self.assertEqual(two, "L04\nL05\nL06\n")
        self.assertEqual(one, "L07\nL08\nL09\n")
        self.assertEqual(current, "L10\n")
        self.assertFalse(os.path.exists(path + ".3"))
        survivors = (two + one + current).splitlines()
        self.assertEqual(survivors, ["L04", "L05", "L06", "L07", "L08", "L09", "L10"])

    def test_backups_zero_keeps_no_old_files(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "only.log")
        log = get_logger("rot0", prefix="")
        with FileSink(path, max_bytes=8, backups=0, render="plain") as fsink:
            add_sink(fsink)
            for idx in range(6):
                log.info(f"M{idx}")
        self.assertFalse(os.path.exists(path + ".1"))
        self.assertLessEqual(os.path.getsize(path), 8)
        self.assertEqual(self._read(path), "M4\nM5\n")

    def test_each_file_within_max_bytes(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "size.log")
        log = get_logger("rotj", prefix="")
        with FileSink(path, max_bytes=200, backups=3, render="json") as fsink:
            add_sink(fsink)
            for idx in range(12):
                log.info(f"m{idx}")
        names = sorted(os.listdir(tmpdir))
        self.assertIn("size.log.1", names)
        self.assertIn("size.log.3", names)
        for name in names:
            full = os.path.join(tmpdir, name)
            self.assertLessEqual(os.path.getsize(full), 200)
            for line in self._read(full).splitlines():
                payload = json.loads(line)
                self.assertEqual(payload["logger"], "rotj")
                self.assertIn(payload["level"], ("DEBUG", "INFO", "WARNING", "ERROR"))

    def test_file_sink_receives_context_fields(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "ctx.log")
        with FileSink(path, max_bytes=10_000, backups=1, render="text") as fsink:
            add_sink(fsink)
            set_context(batch="nightly")
            get_logger("rotc").info("with context")
        self.assertIn("[batch=nightly]", self._read(path))


if __name__ == "__main__":
    unittest.main()
