"""Watcher 与 reference.OpReference 的随机对拍，外加四类翻车现场回归。

老测试一个字不动，这里是新增文件。
"""

import os
import random
import tempfile
import time
import unittest

from snapwatch import (CREATED, DELETED, MODIFIED, MOVED, Event, FileSystem,
                       ManualClock, StatEntry, SysFS, Watcher)
from snapwatch.reference import OpReference, OpScript, publish


def make_file(root, rel, data, clock, stamp=None):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    value = int((clock() if stamp is None else stamp) * 1e9)
    os.utime(path, ns=(value, value))
    return path


class FuzzAgainstReference(unittest.TestCase):
    """随机操作序列配随机扫描时机，事件集合与顺序逐批对齐。"""

    SEEDS = tuple(range(40))
    ROUNDS = 40

    def run_seed(self, seed):
        rng = random.Random(seed * 7919 + 13)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = tmp.name
        clock = ManualClock(1000.0)
        script = OpScript(root, clock, granularity=1.0, seed=seed)
        initial = script.setup(files=10, dirs=3)
        watcher = Watcher(root, fs=SysFS(), clock=clock,
                          timestamp_granularity=1.0)
        reference = OpReference(debounce=0.25)
        reference.prime(initial)

        def sweep(ops, label):
            expected = reference.feed(clock(), ops)
            actual = watcher.poll()
            self.assertEqual(
                actual, expected,
                "%s seed=%d\nactual=%r\nexpected=%r"
                % (label, seed, actual, expected))

        for round_index in range(self.ROUNDS):
            ops = script.step(n_ops=rng.choice((1, 1, 2, 3)))
            # 操作之后、静默之前，随机插若干次扫描练 debounce
            for _ in range(rng.choice((0, 1, 1, 3))):
                clock.advance(rng.uniform(0.0, 0.15))
                sweep(ops, "mid round %d" % round_index)
            clock.advance(rng.uniform(0.2, 0.5))
            sweep(ops, "round %d" % round_index)
            # 随机来一轮什么都没发生的空扫
            if rng.random() < 0.3:
                clock.advance(rng.uniform(0.0, 0.5))
                sweep([], "idle round %d" % round_index)

        # 收尾：把 debounce 里还没发的事件全部逼出来，逐批对齐
        for _ in range(20):
            clock.advance(0.3)
            before = len(watcher._pending)
            sweep([], "drain")
            if before == 0:
                break

    def test_all_seeds(self):
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                self.run_seed(seed)


class AtomicSaveRegression(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.clock = ManualClock(500.0)

    def quiet(self, watcher, rounds=3, step=1.0):
        events = []
        for _ in range(rounds):
            self.clock.advance(step)
            events.extend(watcher.poll())
        return events

    def test_temp_then_rename_is_one_modified(self):
        make_file(self.root, "notes.txt", b"v1", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        self.quiet(watcher)
        tmp = make_file(self.root, "notes.txt.tmp", b"v2", self.clock)
        os.replace(tmp, os.path.join(self.root, "notes.txt"))
        events = self.quiet(watcher)
        self.assertEqual(events, [Event(MODIFIED, "notes.txt", False)])

    def test_save_storm_coalesces_to_one_modified(self):
        make_file(self.root, "notes.txt", b"v1", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        self.quiet(watcher)
        seen = []
        for content in (b"v2", b"v3", b"v4"):
            self.clock.advance(1.2)
            make_file(self.root, "notes.txt", content, self.clock)
            seen.extend(watcher.poll())
        seen.extend(self.quiet(watcher))
        self.assertEqual(seen, [Event(MODIFIED, "notes.txt", False)])

    def test_coarse_timestamp_same_size_second_write(self):
        make_file(self.root, "build.log", b"aaaaaaaa", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        self.quiet(watcher, rounds=2, step=0.2)
        for content in (b"bbbbbbbb", b"cccccccc"):
            self.clock.advance(0.2)
            make_file(self.root, "build.log", content, self.clock,
                      stamp=500.0)
        events = self.quiet(watcher, rounds=4, step=0.2)
        self.assertEqual(events, [Event(MODIFIED, "build.log", False)])


class BlockedFS(SysFS):
    """模拟监听目录被 chmod 掉：scandir 抛权限错误。"""

    def __init__(self, name):
        self.name = name
        self.blocked = False

    def scandir(self, path):
        if self.blocked and path.endswith(os.sep + self.name):
            raise PermissionError(path)
        return super().scandir(path)


class BlockedDirectoryRegression(unittest.TestCase):
    def test_chmod_does_not_report_subtree_deleted(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(500.0)
            for name in ("f1.txt", "f2.txt", "d0/f3.txt"):
                make_file(root, name, b"x", clock)
            filesystem = BlockedFS("d0")
            watcher = Watcher(root, fs=filesystem, clock=clock)
            for _ in range(3):
                clock.advance(1.0)
                self.assertEqual(watcher.poll(), [])
            filesystem.blocked = True
            for _ in range(4):
                clock.advance(1.0)
                self.assertEqual(watcher.poll(), [])
            # 恢复之后仍然什么都不报，子树一条没少
            filesystem.blocked = False
            for _ in range(3):
                clock.advance(1.0)
                self.assertEqual(watcher.poll(), [])
            paths = watcher.snapshot().paths()
            self.assertEqual(
                sorted(paths),
                ["d0", "d0/f3.txt", "f1.txt", "f2.txt"])


class CountingFS(SysFS):
    def __init__(self):
        self.reads = 0

    def read_bytes(self, path):
        self.reads += 1
        return super().read_bytes(path)


class QuietScanNoReads(unittest.TestCase):
    def test_idle_polls_do_not_read_file_contents(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(100.0)
            for index in range(20):
                make_file(root, "d/f%02d.txt" % index,
                          b"content-%d" % index, clock, stamp=0.0)
            filesystem = CountingFS()
            watcher = Watcher(root, fs=filesystem, clock=clock,
                              timestamp_granularity=1.0)
            baseline = filesystem.reads
            for _ in range(3):
                clock.advance(5.0)
                self.assertEqual(watcher.poll(), [])
            self.assertEqual(filesystem.reads, baseline)


class MemoryFS(FileSystem):
    """10 万条目的内存文件系统，用于性能/零读取断言。"""

    def __init__(self, root, count):
        self.root = os.path.abspath(root)
        self.dirs = {"": None}
        self.files = {}
        self.children = {"": set()}
        for index in range(count):
            parent = "d%03d" % (index // 1000)
            self.dirs.setdefault(parent, None)
            self.children.setdefault("", set()).add(parent)
            self.children.setdefault(parent, set())
            self.children[parent].add("f%06d" % index)
            self.files[parent + "/f%06d" % index] = StatEntry(
                0, 8, index + 10, False)

    def _rel(self, path):
        path = os.path.abspath(path)
        if path == self.root:
            return ""
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    def stat(self, path):
        rel = self._rel(path)
        if rel in self.files:
            return self.files[rel]
        if rel in self.dirs:
            return StatEntry(0, 4096, 2_000_000_000 + hash(rel) % 100000,
                             True)
        raise FileNotFoundError(path)

    def scandir(self, path):
        rel = self._rel(path)
        return sorted(self.children.get(rel, set()))

    def read_bytes(self, path):
        raise AssertionError("静止树不该读内容: %r" % path)


class LargeTreePerformance(unittest.TestCase):
    def test_100k_idle_scan_is_fast_and_readless(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        filesystem = MemoryFS(tmp.name, 100_000)
        watcher = Watcher(tmp.name, fs=filesystem, clock=lambda: 10.0,
                          timestamp_granularity=1.0)
        self.assertEqual(len(watcher.snapshot()), 100_100)
        start = time.perf_counter()
        events = watcher.poll()
        elapsed = time.perf_counter() - start
        self.assertEqual(events, [])
        self.assertLess(elapsed, 3.0, "静止扫描耗时 %.2fs" % elapsed)


class EventOrderingSanity(unittest.TestCase):
    def test_batch_order_deleted_modified_moved_created(self):
        f = (False, 1, 10, 1, b"x")
        pairs = [
            ("zz/new", None, f),
            ("zz/old", f, None),
            ("mm", f, (False, 2, 11, 2, b"y")),
            ("aa/src", f, None),
            ("aa/dst", None, f),
        ]
        events = publish(pairs)
        kinds = [event.kind for event in events]
        self.assertEqual(kinds, [DELETED, MODIFIED, MOVED, CREATED])
        self.assertEqual(
            events,
            [Event(DELETED, "zz/old", False),
             Event(MODIFIED, "mm", False),
             Event(MOVED, "aa/src", False, "aa/dst"),
             Event(CREATED, "zz/new", False)])


if __name__ == "__main__":
    unittest.main()
