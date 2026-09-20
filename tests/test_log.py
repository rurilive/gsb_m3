"""结构化日志层测试：捕获、级别过滤、并发上下文隔离、文件轮转。"""

import io
import os
import tempfile
import threading
import unittest

from loglite import log as logmod
from loglite.log import (
    INFO,
    WARNING,
    RotatingFileSink,
    StreamSink,
    add_sink,
    clear_context,
    clear_sinks,
    get_context,
    get_logger,
    reset,
    set_context,
    set_level,
)


class LogTestCase(unittest.TestCase):
    def setUp(self):
        reset()

    def tearDown(self):
        reset()

    def buffer_sink(self, compat=False):
        buf = io.StringIO()
        clear_sinks()
        add_sink(StreamSink(buf, compat=compat))
        return buf


class TestCapture(LogTestCase):
    def test_compat_line_matches_legacy_print(self):
        buf = self.buffer_sink(compat=True)
        get_logger("t").info("[scanner] start: 4 entries")
        self.assertEqual(buf.getvalue(), "[scanner] start: 4 entries\n")

    def test_structured_line_has_level_and_context(self):
        buf = self.buffer_sink()
        set_context(stage="scan", run=7)
        get_logger("t").warning("watch out")
        self.assertEqual(buf.getvalue(), "WARNING watch out stage=scan run=7\n")

    def test_clear_context_drops_fields(self):
        buf = self.buffer_sink()
        set_context(stage="scan")
        clear_context()
        self.assertEqual(get_context(), {})
        get_logger("t").warning("plain")
        self.assertEqual(buf.getvalue(), "WARNING plain\n")

    def test_set_context_merges_fields(self):
        set_context(a=1)
        set_context(b=2)
        self.assertEqual(get_context(), {"a": 1, "b": 2})

    def test_default_sink_writes_to_current_stdout(self):
        # 默认兼容 stdout sink 跟随 redirect_stdout，模块输出与旧 print 一致
        from loglite.scanner import scan

        buf = io.StringIO()
        from contextlib import redirect_stdout

        with redirect_stdout(buf):
            scan([("x.tmp", 1, 1)])
        self.assertEqual(
            buf.getvalue().splitlines(),
            [
                "[scanner] start: 1 entries",
                "[scanner] flagged x.tmp (temp suffix)",
                "[scanner] done: 0 ok, 1 flagged",
            ],
        )


class TestLevelFilter(LogTestCase):
    def test_below_level_dropped(self):
        buf = self.buffer_sink()
        logger = get_logger("t")
        set_level(WARNING)
        logger.debug("d")
        logger.info("i")
        self.assertEqual(buf.getvalue(), "")
        logger.warning("w")
        logger.error("e")
        self.assertEqual(buf.getvalue().splitlines(), ["WARNING w", "ERROR e"])

    def test_default_level_is_info(self):
        buf = self.buffer_sink()
        logger = get_logger("t")
        logger.debug("hidden")
        logger.info("shown")
        self.assertEqual(buf.getvalue(), "INFO shown\n")


class TestContextIsolation(LogTestCase):
    def test_context_is_thread_local(self):
        buf = self.buffer_sink()
        logger = get_logger("t")
        set_context(main=True)
        entered = [threading.Event(), threading.Event()]

        def worker(idx, tag):
            set_context(worker=tag)
            self.assertNotIn("main", get_context())
            entered[idx].set()
            entered[1 - idx].wait(timeout=5)  # 两个线程都设好上下文再写日志
            logger.info(f"from {tag}")

        threads = [
            threading.Thread(target=worker, args=(0, "alpha")),
            threading.Thread(target=worker, args=(1, "beta")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        lines = sorted(buf.getvalue().splitlines())
        self.assertEqual(
            lines,
            ["INFO from alpha worker=alpha", "INFO from beta worker=beta"],
        )
        # 主线程上下文不受子线程影响
        self.assertEqual(get_context(), {"main": True})


class TestRotation(LogTestCase):
    def test_rotation_shifts_and_deletes(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "app.log")
            clear_sinks()
            add_sink(RotatingFileSink(path, max_bytes=40, backups=2, compat=True))
            logger = get_logger("t")
            # 每行 10 字节，max_bytes=40 -> 每文件 4 行；写 14 行触发 3 次轮转
            for i in range(14):
                logger.info(f"line-{i:04d}")

            def lines(p):
                with open(p, encoding="utf-8") as f:
                    return f.read().splitlines()

            self.assertEqual(lines(path), ["line-0012", "line-0013"])
            self.assertEqual(
                lines(path + ".1"),
                ["line-0008", "line-0009", "line-0010", "line-0011"],
            )
            self.assertEqual(
                lines(path + ".2"),
                ["line-0004", "line-0005", "line-0006", "line-0007"],
            )
            # 只留 backups 个旧文件，更旧的已删除
            self.assertFalse(os.path.exists(path + ".3"))

    def test_rotation_keeps_structured_rendering(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "app.log")
            clear_sinks()
            add_sink(RotatingFileSink(path, max_bytes=1024, backups=1))
            set_context(stage="scan")
            get_logger("t").info("hello")
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "INFO hello stage=scan\n")

    def test_invalid_rotation_params_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "app.log")
            with self.assertRaises(ValueError):
                RotatingFileSink(path, max_bytes=0, backups=1)
            with self.assertRaises(ValueError):
                RotatingFileSink(path, max_bytes=10, backups=0)


if __name__ == "__main__":
    unittest.main()
