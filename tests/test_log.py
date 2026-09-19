"""结构化日志层（loglite/log.py）行为测试。

覆盖：sink 捕获与渲染、级别过滤、线程上下文隔离（Event 定节奏）、文件轮转。
每个用例前后 reset()，不影响 test_pipeline 锁定的 stdout 基线。
"""

import io
import os
import shutil
import tempfile
import threading
import unittest

from loglite import log as logmod


class ListSink:
    """线程安全的内存 sink，按行收集 emit 的文本。"""

    def __init__(self):
        self.lines = []
        self._lock = threading.Lock()

    def emit(self, text):
        with self._lock:
            self.lines.append(text)


class LogTestCase(unittest.TestCase):
    def setUp(self):
        logmod.reset()

    def tearDown(self):
        logmod.reset()

    def use_sink(self, sink):
        logmod.clear_sinks()
        logmod.add_sink(sink)
        return sink


class TestCapture(LogTestCase):
    def test_compat_renders_bare_message(self):
        buf = io.StringIO()
        self.use_sink(logmod.StreamSink(buf))
        logmod.get_logger("demo").info("[scanner] start: 1 entries")
        self.assertEqual(buf.getvalue(), "[scanner] start: 1 entries\n")

    def test_structured_renders_level_name_and_context(self):
        sink = self.use_sink(ListSink())
        logmod.set_compat(False)
        logmod.set_context(run=7, stage="scan")
        logmod.get_logger("demo").warning("watch out")
        self.assertEqual(sink.lines, ["WARNING demo run=7 stage=scan watch out"])

    def test_clear_context_drops_fields(self):
        sink = self.use_sink(ListSink())
        logmod.set_compat(False)
        logmod.set_context(run=7)
        logmod.clear_context()
        logmod.get_logger("demo").info("hello")
        self.assertEqual(sink.lines, ["INFO demo hello"])

    def test_context_accepts_mapping_and_kwargs(self):
        sink = self.use_sink(ListSink())
        logmod.set_compat(False)
        logmod.set_context({"run": 1})
        logmod.set_context(stage="plan")
        logmod.get_logger("demo").info("go")
        self.assertEqual(sink.lines, ["INFO demo run=1 stage=plan go"])


class TestLevelFilter(LogTestCase):
    def test_default_level_drops_debug(self):
        sink = self.use_sink(ListSink())
        logger = logmod.get_logger("lvl")
        logger.debug("d")
        logger.info("i")
        self.assertEqual(sink.lines, ["i"])

    def test_set_level_filters_below(self):
        sink = self.use_sink(ListSink())
        logger = logmod.get_logger("lvl")
        logmod.set_level(logmod.WARNING)
        logger.debug("d")
        logger.info("i")
        logger.warning("w")
        logger.error("e")
        self.assertEqual(sink.lines, ["w", "e"])

    def test_set_level_accepts_names(self):
        sink = self.use_sink(ListSink())
        logger = logmod.get_logger("lvl")
        logmod.set_level("ERROR")
        logger.warning("w")
        logger.error("e")
        self.assertEqual(sink.lines, ["e"])
        logmod.set_level("DEBUG")
        logger.debug("d")
        self.assertEqual(sink.lines, ["e", "d"])


class TestContextIsolation(LogTestCase):
    def test_threads_do_not_share_context(self):
        sink = self.use_sink(ListSink())
        logmod.set_compat(False)
        logger = logmod.get_logger("t")
        a_set = threading.Event()
        b_set = threading.Event()

        def worker(name, mine, other):
            logmod.set_context(worker=name)
            mine.set()        # 本线程上下文已就位
            other.wait(5)     # 等对方也设置完再发日志：若共享存储，后写会覆盖先写
            logger.info("hello")

        ta = threading.Thread(target=worker, args=("A", a_set, b_set))
        tb = threading.Thread(target=worker, args=("B", b_set, a_set))
        ta.start()
        tb.start()
        ta.join(5)
        tb.join(5)
        self.assertFalse(ta.is_alive() or tb.is_alive())
        self.assertEqual(
            sorted(sink.lines),
            ["INFO t worker=A hello", "INFO t worker=B hello"],
        )
        # 主线程上下文不受子线程影响
        logger.info("main")
        self.assertEqual(sink.lines[-1], "INFO t main")


class TestRotation(LogTestCase):
    def setUp(self):
        super().setUp()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        super().tearDown()

    def read_lines(self, name):
        with open(os.path.join(self.tmpdir, name), encoding="utf-8") as f:
            return f.read().splitlines()

    def test_rotation_shifts_and_drops_oldest(self):
        path = os.path.join(self.tmpdir, "app.log")
        self.use_sink(logmod.RotatingFileSink(path, max_bytes=20, backups=2))
        logger = logmod.get_logger("rot")
        for i in range(10):
            logger.info(f"line-{i}")  # 每条 7 字节，每个文件正好容 2 条
        self.assertEqual(self.read_lines("app.log"), ["line-8", "line-9"])
        self.assertEqual(self.read_lines("app.log.1"), ["line-6", "line-7"])
        self.assertEqual(self.read_lines("app.log.2"), ["line-4", "line-5"])
        self.assertFalse(os.path.exists(path + ".3"))

    def test_no_rotation_under_limit(self):
        path = os.path.join(self.tmpdir, "small.log")
        self.use_sink(logmod.RotatingFileSink(path, max_bytes=100, backups=1))
        logmod.get_logger("rot").info("short")
        self.assertEqual(self.read_lines("small.log"), ["short"])
        self.assertFalse(os.path.exists(path + ".1"))


if __name__ == "__main__":
    unittest.main()
