"""本轮 bugfix 的回归测试：原子改名、连发合并、秒级时间戳、目录失读、
对拍一致性和十万文件的静止扫描性能。原有测试一个字没动。"""

import os
import random
import tempfile
import time
import unittest

from snapwatch import (MODIFIED, MOVED, Event, ManualClock, OpReference,
                       OpScript, SysFS, Watcher)
from snapwatch.fs import FileSystem, StatEntry


def make_file(root, rel, data, clock, stamp=None):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    value = int((clock() if stamp is None else stamp) * 1e9)
    os.utime(path, ns=(value, value))
    return path


def settle(watcher, clock, rounds=6, step=1.0):
    """把时钟推过 debounce，收齐挂起的事件。"""
    events = []
    for _ in range(rounds):
        clock.advance(step)
        events.extend(watcher.poll())
    return events


class AtomicSaveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.clock = ManualClock(500.0)

    def test_replace_over_existing_file_is_modified(self):
        make_file(self.root, "notes.txt", b"v1", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        settle(watcher, self.clock)
        tmp = make_file(self.root, "notes.txt.tmp", b"v2", self.clock)
        os.replace(tmp, os.path.join(self.root, "notes.txt"))
        events = settle(watcher, self.clock)
        self.assertEqual(events, [Event(MODIFIED, "notes.txt", False)])

    def test_tmp_seen_by_a_midway_scan_is_silent(self):
        make_file(self.root, "notes.txt", b"v1", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        settle(watcher, self.clock)
        make_file(self.root, "notes.txt.tmp", b"v2", self.clock)
        self.clock.advance(0.1)
        self.assertEqual(watcher.poll(), [])
        os.replace(os.path.join(self.root, "notes.txt.tmp"),
                   os.path.join(self.root, "notes.txt"))
        self.clock.advance(0.1)
        self.assertEqual(watcher.poll(), [])
        events = settle(watcher, self.clock)
        self.assertEqual(events, [Event(MODIFIED, "notes.txt", False)])


class CoalesceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.clock = ManualClock(500.0)

    def test_repeated_writes_become_one_event(self):
        make_file(self.root, "notes.txt", b"v1", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        settle(watcher, self.clock)
        for content in (b"v2", b"v3", b"v4"):
            self.clock.advance(1.2)
            make_file(self.root, "notes.txt", content, self.clock)
            watcher.poll()
        events = settle(watcher, self.clock)
        self.assertEqual(events, [Event(MODIFIED, "notes.txt", False)])

    def test_change_reverted_before_debounce_is_silent(self):
        make_file(self.root, "notes.txt", b"v1", self.clock)
        old_mtime = self.clock()
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        settle(watcher, self.clock)
        self.clock.advance(1.0)
        make_file(self.root, "notes.txt", b"v2", self.clock)
        self.clock.advance(0.1)
        self.assertEqual(watcher.poll(), [])
        make_file(self.root, "notes.txt", b"v1", self.clock,
                  stamp=old_mtime)
        self.assertEqual(settle(watcher, self.clock), [])

    def test_appear_then_disappear_is_silent(self):
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        settle(watcher, self.clock)
        make_file(self.root, "ghost", b"x", self.clock)
        self.clock.advance(0.1)
        self.assertEqual(watcher.poll(), [])
        os.remove(os.path.join(self.root, "ghost"))
        self.assertEqual(settle(watcher, self.clock), [])


class CoarseTimestampTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.clock = ManualClock(500.0)

    def test_same_second_same_size_rewrite_is_detected(self):
        make_file(self.root, "build.log", b"aaaaaaaa", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        self.clock.advance(0.2)
        watcher.poll()
        self.clock.advance(0.2)
        for content in (b"bbbbbbbb", b"cccccccc"):
            make_file(self.root, "build.log", content, self.clock,
                      stamp=500.0)
        events = settle(watcher, self.clock, rounds=4, step=0.2)
        self.assertEqual(events, [Event(MODIFIED, "build.log", False)])


class MemFS(FileSystem):
    """内存文件系统：节点是 (is_dir, bytes, mtime_ns, inode)。"""

    def __init__(self, root="/root"):
        self.root = os.path.abspath(root)
        self.nodes = {self.root: (True, b"", 0, 0)}
        self.children = {self.root: set()}
        self._next_inode = 1
        self.read_count = 0
        self.unreadable_dirs = set()

    def _rel(self, path):
        path = os.path.abspath(path)
        return "" if path == self.root else os.path.relpath(
            path, self.root).replace(os.sep, "/")

    def _abs(self, rel):
        return self.root if not rel else self.root + "/" + rel

    def create_file(self, path, data=b"", mtime_ns=0):
        rel = self._rel(path) if os.path.isabs(path) else path
        parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
        if parent:
            self.mkdir(parent)
        inode = self._next_inode
        self._next_inode += 1
        self.nodes[self._abs(rel)] = (False, bytes(data), mtime_ns, inode)
        self.children[self._abs(parent)].add(rel.rsplit("/", 1)[-1])
        return rel

    def mkdir(self, path, mtime_ns=0):
        rel = self._rel(path) if os.path.isabs(path) else path
        parts = [part for part in rel.split("/") if part]
        current = ""
        parent = self.root
        for index, part in enumerate(parts):
            current = part if index == 0 else current + "/" + part
            key = self._abs(current)
            if key not in self.nodes:
                inode = self._next_inode
                self._next_inode += 1
                self.nodes[key] = (True, b"", mtime_ns, inode)
                self.children[key] = set()
                self.children[parent].add(part)
            parent = key

    def write(self, path, data, mtime_ns=None):
        key = os.path.abspath(path) if os.path.isabs(path) else self._abs(path)
        is_dir, old_data, old_mtime, inode = self.nodes[key]
        self.nodes[key] = (False, bytes(data),
                           old_mtime if mtime_ns is None else mtime_ns,
                           inode)

    def rename(self, src, dst):
        src_rel = self._rel(src) if os.path.isabs(src) else src
        dst_rel = self._rel(dst) if os.path.isabs(dst) else dst
        src_parent = src_rel.rsplit("/", 1)[0] if "/" in src_rel else ""
        dst_parent = dst_rel.rsplit("/", 1)[0] if "/" in dst_rel else ""
        self.nodes[self._abs(dst_rel)] = self.nodes.pop(self._abs(src_rel))
        self.children[self._abs(src_parent)].discard(
            src_rel.rsplit("/", 1)[-1])
        self.children.setdefault(self._abs(dst_parent), set()).add(
            dst_rel.rsplit("/", 1)[-1])

    def remove(self, path):
        key = os.path.abspath(path) if os.path.isabs(path) else self._abs(path)
        del self.nodes[key]

    def stat(self, path):
        key = os.path.abspath(path)
        if key not in self.nodes:
            raise FileNotFoundError(path)
        is_dir, data, mtime_ns, inode = self.nodes[key]
        return StatEntry(mtime_ns, len(data), inode, is_dir)

    def scandir(self, path):
        rel = self._rel(path)
        if rel in self.unreadable_dirs:
            raise PermissionError(path)
        key = os.path.abspath(path)
        if key not in self.nodes:
            raise FileNotFoundError(path)
        return sorted(self.children.get(key, ()))

    def read_bytes(self, path):
        self.read_count += 1
        return self.nodes[os.path.abspath(path)][1]


class BlockedDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.fs = MemFS()
        self.clock = ManualClock(100.0)
        for name in ("d0/f1.txt", "d0/f2.txt", "d0/sub/f3.txt",
                     "outside.txt"):
            self.fs.create_file(name, b"x", mtime_ns=90_000_000_000)
        self.watcher = Watcher("/root", fs=self.fs, clock=self.clock)

    def test_chmod_does_not_report_subtree_deleted(self):
        self.assertEqual(self.watcher.poll(), [])
        reads = self.fs.read_count
        self.fs.unreadable_dirs.add("d0")
        self.clock.advance(2.0)
        self.assertEqual(settle(self.watcher, self.clock), [])
        self.assertEqual(self.fs.read_count, reads)

    def test_recovery_reports_later_real_change(self):
        self.clock.advance(2.0)
        self.watcher.poll()
        self.fs.unreadable_dirs.add("d0")
        self.clock.advance(2.0)
        self.watcher.poll()
        self.fs.unreadable_dirs.discard("d0")
        self.fs.write("d0/f1.txt", b"different content here",
                      mtime_ns=int((self.clock() + 10.0) * 1e9))
        events = settle(self.watcher, self.clock)
        self.assertEqual(events, [Event(MODIFIED, "d0/f1.txt", False)])

    def test_blocked_root_does_not_report_everything_deleted(self):
        self.fs.unreadable_dirs.add("")
        self.clock.advance(2.0)
        self.assertEqual(settle(self.watcher, self.clock), [])
        self.fs.unreadable_dirs.discard("")
        self.clock.advance(2.0)
        self.assertEqual(settle(self.watcher, self.clock), [])


class LargeTreeTests(unittest.TestCase):
    def _build(self, count):
        fs = MemFS()
        for index in range(count):
            fs.mkdir("dir%03d" % (index % 200))
            fs.create_file("dir%03d/f%06d.txt" % (index % 200, index),
                           b"data-%d" % index, mtime_ns=50_000_000_000)
        return fs

    def test_steady_scan_reads_no_contents(self):
        fs = self._build(100_000)
        clock = ManualClock(1000.0)
        watcher = Watcher("/root", fs=fs, clock=clock)
        self.assertEqual(fs.read_count, 0)
        started = time.perf_counter()
        clock.advance(60.0)
        self.assertEqual(watcher.poll(), [])
        elapsed = time.perf_counter() - started
        self.assertEqual(fs.read_count, 0)
        self.assertLess(elapsed, 5.0,
                        "静止扫描十万节点耗时 %.2fs" % elapsed)
        self.assertEqual(len(watcher.snapshot()), 100_000 + 200)

    def test_changed_file_is_hashed_once(self):
        fs = self._build(1_000)
        clock = ManualClock(1000.0)
        watcher = Watcher("/root", fs=fs, clock=clock)
        clock.advance(60.0)
        watcher.poll()
        self.assertEqual(fs.read_count, 0)
        fs.write("dir000/f000000.txt", b"changed",
                 mtime_ns=int(clock() * 1e9))
        clock.advance(1.0)
        self.assertEqual(watcher.poll(), [])
        self.assertEqual(fs.read_count, 1)
        events = settle(watcher, clock)
        self.assertEqual(events,
                         [Event(MODIFIED, "dir000/f000000.txt", False)])


class EventOrderTests(unittest.TestCase):
    def setUp(self):
        self.fs = MemFS()
        self.clock = ManualClock(100.0)
        self.fs.create_file("a/b/old.txt", b"1",
                            mtime_ns=90_000_000_000)
        self.fs.create_file("edit.txt", b"1", mtime_ns=90_000_000_000)
        self.watcher = Watcher("/root", fs=self.fs, clock=self.clock)

    def test_deleted_modified_moved_created_order(self):
        self.clock.advance(2.0)
        self.watcher.poll()
        now_ns = int(self.clock() * 1e9)
        self.fs.remove("a/b/old.txt")
        self.fs.write("edit.txt", b"22", mtime_ns=now_ns)
        self.fs.mkdir("a/newdir", mtime_ns=now_ns)
        self.fs.create_file("a/newdir/inner.txt", b"4", mtime_ns=now_ns)
        self.fs.create_file("a/b/new.txt", b"3", mtime_ns=now_ns)
        events = settle(self.watcher, self.clock)
        self.assertEqual(
            [(event.kind, event.path) for event in events],
            [("deleted", "a/b/old.txt"),
             ("modified", "edit.txt"),
             ("created", "a/newdir"),
             ("created", "a/b/new.txt"),
             ("created", "a/newdir/inner.txt")])

    def test_move_is_paired(self):
        self.clock.advance(2.0)
        self.watcher.poll()
        self.fs.rename("a/b/old.txt", "a/b/moved.txt")
        events = settle(self.watcher, self.clock)
        self.assertEqual(
            events,
            [Event(MOVED, "a/b/old.txt", False, "a/b/moved.txt")])


class ReferenceFuzzTests(unittest.TestCase):
    """随机操作序列配随机扫描时机，Watcher 与 OpReference 严格对齐。"""

    GRANULARITIES = (0.5, 1.0, 2.0)
    SEEDS = (1, 2, 3, 7, 42)
    GAPS = (0.0, 0.01, 0.05, 0.2, 0.24, 0.25, 0.26, 0.4, 0.9, 2.0)

    def _run(self, seed, granularity):
        rng = random.Random(seed * 131 + int(granularity * 1000))
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(10000.0)
            script = OpScript(root, clock, granularity=granularity,
                              seed=seed * 7919 + 3)
            ref = OpReference(debounce=0.25)
            ref.prime(script.setup(files=14, dirs=4))
            watcher = Watcher(root, fs=SysFS(), clock=clock,
                              debounce=0.25, resolution=granularity)
            for round_index in range(80):
                ops = script.step(rng.randrange(0, 5))
                clock.advance(self.GAPS[rng.randrange(len(self.GAPS))])
                expected = ref.feed(clock(), ops)
                actual = watcher.poll()
                if expected != actual:
                    return round_index, ops, expected, actual
        return None

    def test_random_sequences_match_reference(self):
        for granularity in self.GRANULARITIES:
            for seed in self.SEEDS:
                mismatch = self._run(seed, granularity)
                if mismatch is not None:
                    round_index, ops, expected, actual = mismatch
                    self.fail(
                        "granularity=%s seed=%s round=%s\nops=%r\n"
                        "expected=%r\nactual=%r"
                        % (granularity, seed, round_index, ops,
                           expected, actual))
