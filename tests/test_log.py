"""结构化日志层测试：捕获、级别过滤、并发上下文隔离、文件轮转。"""

import io
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stdout

from loglite import log


class ListSink:
    """测试用 sink：把 emit 的行收进列表。"""

    def __init__(self):
        self.lines = []

    def emit(self, line):
        self.lines.append(line)


class LogTestCase(unittest.TestCase):
    def setUp(self):
        log.set_level("INFO")
        log.set_structured(False)
        log.reset_sinks()
        log.clear_context()

    tearDown = setUp


class TestCapture(LogTestCase):
    def test_default_sink_writes_stdout(self):
        logger = log.get_logger("t")
        buf = io.StringIO()
        with redirect_stdout(buf):
            logger.info("hello")
        self.assertEqual(buf.getvalue(), "hello\n")

    def test_added_sink_receives_lines(self):
        sink = ListSink()
        log.add_sink(sink)
        logger = log.get_logger("t")
        with redirect_stdout(io.StringIO()):
            logger.info("captured")
        self.assertEqual(sink.lines, ["captured"])

    def test_compat_prefix_matches_legacy_print(self):
        logger = log.get_logger("scanner", compat_prefix="[scanner]")
        buf = io.StringIO()
        with redirect_stdout(buf):
            logger.info("start: 4 entries")
        self.assertEqual(buf.getvalue(), "[scanner] start: 4 entries\n")

    def test_structured_renders_level_name_context(self):
        log.set_structured(True)
        log.set_context(stage="scan", run=7)
        sink = ListSink()
        log.add_sink(sink)
        logger = log.get_logger("scanner", compat_prefix="[scanner]")
        with redirect_stdout(io.StringIO()):
            logger.info("start")
        self.assertEqual(sink.lines, ["INFO [scanner] start stage=scan run=7"])


class TestLevels(LogTestCase):
    def test_below_level_not_emitted(self):
        sink = ListSink()
        log.add_sink(sink)
        logger = log.get_logger("t")
        with redirect_stdout(io.StringIO()):
            log.set_level("WARNING")
            logger.debug("d")
            logger.info("i")
            logger.warning("w")
            logger.error("e")
        self.assertEqual(sink.lines, ["w", "e"])

    def test_debug_level_passes_everything(self):
        sink = ListSink()
        log.add_sink(sink)
        logger = log.get_logger("t")
        with redirect_stdout(io.StringIO()):
            log.set_level("DEBUG")
            logger.debug("d")
            logger.info("i")
        self.assertEqual(sink.lines, ["d", "i"])

    def test_unknown_level_rejected(self):
        with self.assertRaises(ValueError):
            log.set_level("VERBOSE")


class TestContext(LogTestCase):
    def test_clear_context_removes_fields(self):
        log.set_structured(True)
        sink = ListSink()
        log.add_sink(sink)
        logger = log.get_logger("t")
        with redirect_stdout(io.StringIO()):
            log.set_context(who="main")
            logger.info("with-ctx")
            log.clear_context()
            logger.info("without-ctx")
        self.assertEqual(sink.lines, ["INFO [t] with-ctx who=main", "INFO [t] without-ctx"])

    def test_context_isolated_between_threads(self):
        log.set_structured(True)
        sink = ListSink()
        log.add_sink(sink)
        logger = log.get_logger("t")
        worker_ctx_set = threading.Event()
        main_logged = threading.Event()
        worker_logged = threading.Event()

        def worker():
            log.set_context(who="worker")
            worker_ctx_set.set()
            main_logged.wait(5)  # 等主线程先打一条，确认互不串
            logger.info("from-worker")
            worker_logged.set()

        t = threading.Thread(target=worker)
        with redirect_stdout(io.StringIO()):
            t.start()
            self.assertTrue(worker_ctx_set.wait(5))
            logger.info("from-main")  # 主线程无上下文，不应看到 who=worker
            main_logged.set()
            self.assertTrue(worker_logged.wait(5))
            t.join()
        self.assertIn("INFO [t] from-main", sink.lines)
        self.assertIn("INFO [t] from-worker who=worker", sink.lines)


class TestRotation(LogTestCase):
    @staticmethod
    def _read(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().splitlines()

    def test_rotation_shifts_and_caps_backups(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "app.log")
            sink = log.RotatingFileSink(path, max_bytes=20, backups=2)
            for i in range(6):  # 每行 7 字节，每满 3 行触发一次轮转
                sink.emit(f"line-{i}")
            self.assertEqual(self._read(path), ["line-4", "line-5"])
            self.assertEqual(self._read(path + ".1"), ["line-2", "line-3"])
            self.assertEqual(self._read(path + ".2"), ["line-0", "line-1"])
            self.assertFalse(os.path.exists(path + ".3"))

    def test_older_than_backups_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "app.log")
            sink = log.RotatingFileSink(path, max_bytes=20, backups=2)
            for i in range(8):
                sink.emit(f"line-{i}")
            self.assertEqual(self._read(path), ["line-6", "line-7"])
            self.assertEqual(self._read(path + ".1"), ["line-4", "line-5"])
            self.assertEqual(self._read(path + ".2"), ["line-2", "line-3"])
            # line-0/line-1 已超出 backups 上限，彻底删除
            remaining = []
            for name in os.listdir(d):
                remaining.extend(self._read(os.path.join(d, name)))
            self.assertNotIn("line-0", remaining)
            self.assertNotIn("line-1", remaining)


if __name__ == "__main__":
    unittest.main()
