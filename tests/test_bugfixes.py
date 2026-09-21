"""四个翻车现场的修复锁定，加上对拍、排序和性能测试。

tests/test_watcher.py 与 tests/test_snapshot.py 保持不动，这里是新增覆盖：
原子改名、连写合并、秒级时间戳同尺寸改写、chmod 误删、批内顺序、
出现又消失、随机操作序列对拍 reference、十万文件静止扫描不读内容。
"""

import os
import random
import tempfile
import time
import unittest

from snapwatch import (CREATED, DELETED, MODIFIED, MOVED, Event, ManualClock,
                       SysFS, Watcher)
from snapwatch.fs import FileSystem, StatEntry
from snapwatch.reference import OpReference, OpScript


def make_file(root, rel, data, clock, stamp=None):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    value = int((clock() if stamp is None else stamp) * 1e9)
    os.utime(path, ns=(value, value))
    return path


def drain(watcher, clock, rounds=4, step=1.0):
    events = []
    for _ in range(rounds):
        clock.advance(step)
        events.extend(watcher.poll())
    return events


class ReadCountingFS(SysFS):
    """统计 read_bytes 被调用了多少次，用来证明静止扫描不读内容。"""

    def __init__(self):
        self.reads = 0

    def read_bytes(self, path):
        self.reads += 1
        return super().read_bytes(path)


class BlockedFS(SysFS):
    def __init__(self, blocked_names=()):
        self.blocked_names = set(blocked_names)

    def scandir(self, path):
        if os.path.basename(path) in self.blocked_names:
            raise PermissionError(path)
        return super().scandir(path)


class TestAtomicSave(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.clock = ManualClock(1000.0)

    def test_temp_then_rename_is_one_modified(self):
        make_file(self.root, "notes.txt", b"v1", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        drain(watcher, self.clock)
        tmp = make_file(self.root, "notes.txt.tmp", b"v2-new-body",
                        self.clock)
        os.replace(tmp, os.path.join(self.root, "notes.txt"))
        self.assertEqual(drain(watcher, self.clock),
                         [Event(MODIFIED, "notes.txt", False)])

    def test_repeated_writes_coalesce(self):
        make_file(self.root, "notes.txt", b"v1", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        drain(watcher, self.clock)
        seen = []
        watcher.subscribe(seen.append)
        for content in (b"v2", b"v3", b"v4-final"):
            self.clock.advance(0.2)
            make_file(self.root, "notes.txt", content, self.clock)
            self.assertEqual(watcher.poll(), [])
        self.assertEqual(drain(watcher, self.clock),
                         [Event(MODIFIED, "notes.txt", False)])
        self.assertEqual(len(seen), 1)

    def test_writes_settled_between_scans_are_separate(self):
        make_file(self.root, "notes.txt", b"v1", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        drain(watcher, self.clock)
        make_file(self.root, "notes.txt", b"v2", self.clock)
        self.assertEqual(drain(watcher, self.clock),
                         [Event(MODIFIED, "notes.txt", False)])
        self.clock.advance(2.0)
        make_file(self.root, "notes.txt", b"v3", self.clock)
        self.assertEqual(drain(watcher, self.clock),
                         [Event(MODIFIED, "notes.txt", False)])


class TestCoarseTimestamps(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.clock = ManualClock(1000.0)

    def test_same_second_same_size_change_is_detected(self):
        make_file(self.root, "build.log", b"aaaaaaaa", self.clock,
                  stamp=1000.0)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        drain(watcher, self.clock, rounds=2, step=0.2)
        make_file(self.root, "build.log", b"bbbbbbbb", self.clock,
                  stamp=1000.0)
        self.clock.advance(0.2)
        watcher.poll()
        make_file(self.root, "build.log", b"cccccccc", self.clock,
                  stamp=1000.0)
        self.clock.advance(0.2)
        events = watcher.poll()
        events.extend(drain(watcher, self.clock, rounds=3, step=0.2))
        self.assertEqual(events, [Event(MODIFIED, "build.log", False)])

    def test_touch_without_content_change_is_silent(self):
        make_file(self.root, "same.log", b"abcdefgh", self.clock,
                  stamp=1000.0)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        drain(watcher, self.clock, rounds=2, step=0.2)
        path = os.path.join(self.root, "same.log")
        os.utime(path, ns=(1000 * 10**9, 1000 * 10**9))
        self.assertEqual(drain(watcher, self.clock, rounds=3, step=0.2), [])


class TestBlockedDirectory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.clock = ManualClock(1000.0)

    def test_chmod_subdir_does_not_report_deletions(self):
        for name in ("f1.txt", "f2.txt", "f3.txt"):
            make_file(self.root, "d0/" + name, b"x", self.clock)
        filesystem = BlockedFS()
        watcher = Watcher(self.root, fs=filesystem, clock=self.clock)
        drain(watcher, self.clock)
        filesystem.blocked_names.add("d0")
        self.assertEqual(drain(watcher, self.clock), [])
        self.assertIn("d0/f1.txt", watcher.snapshot().entries)
        make_file(self.root, "outside.txt", b"y", self.clock)
        events = drain(watcher, self.clock)
        self.assertEqual(events, [Event(CREATED, "outside.txt", False)])

    def test_chmod_root_keeps_whole_tree(self):
        for name in ("a.txt", "sub/b.txt"):
            make_file(self.root, name, b"x", self.clock)
        filesystem = BlockedFS()
        watcher = Watcher(self.root, fs=filesystem, clock=self.clock)
        drain(watcher, self.clock)
        filesystem.blocked_names.add(os.path.basename(self.root))
        self.assertEqual(drain(watcher, self.clock), [])
        self.assertEqual(len(watcher.snapshot()), 3)

    def test_recovery_reports_real_deletion(self):
        make_file(self.root, "d0/f1.txt", b"x", self.clock)
        filesystem = BlockedFS()
        watcher = Watcher(self.root, fs=filesystem, clock=self.clock)
        drain(watcher, self.clock)
        filesystem.blocked_names.add("d0")
        self.assertEqual(drain(watcher, self.clock), [])
        filesystem.blocked_names.clear()
        os.remove(os.path.join(self.root, "d0", "f1.txt"))
        events = drain(watcher, self.clock)
        self.assertIn(Event(DELETED, "d0/f1.txt", False), events)
        deletions = [event for event in events if event.kind == DELETED]
        self.assertEqual(deletions,
                         [Event(DELETED, "d0/f1.txt", False)])


class TestTransientChanges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.clock = ManualClock(1000.0)

    def test_appear_and_disappear_between_polls_is_silent(self):
        make_file(self.root, "keeper.txt", b"k", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        drain(watcher, self.clock)
        flash = os.path.join(self.root, "flash.txt")
        with open(flash, "wb") as handle:
            handle.write(b"boom")
        os.remove(flash)
        self.assertEqual(drain(watcher, self.clock), [])

    def test_change_reverted_before_settle_is_silent(self):
        make_file(self.root, "f.txt", b"aaaa", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        drain(watcher, self.clock)
        make_file(self.root, "f.txt", b"bbbb", self.clock)
        self.clock.advance(0.1)
        self.assertEqual(watcher.poll(), [])
        make_file(self.root, "f.txt", b"aaaa", self.clock, stamp=1000.0)
        self.assertEqual(drain(watcher, self.clock), [])


class _Node:
    __slots__ = ("is_dir", "size", "mtime_ns", "inode", "data", "children")

    def __init__(self, is_dir, mtime_ns, inode, data=b""):
        self.is_dir = is_dir
        self.size = len(data)
        self.mtime_ns = mtime_ns
        self.inode = inode
        self.data = data
        self.children = {} if is_dir else None


class _MemoryFS(FileSystem):
    """纯内存文件系统，目录 mtime 不动，排序测试可以精确控制事件。"""

    def __init__(self, root="/root"):
        self.root = root
        self.reads = 0
        self._seq = 0
        self.nodes = {root: _Node(True, -10**18, self._inode())}

    def _inode(self):
        self._seq += 1
        return self._seq

    def _parts(self, rel):
        return os.path.join(self.root, rel).rsplit("/", 1)

    def mkdir(self, rel):
        parent, name = self._parts(rel)
        node = _Node(True, -10**18, self._inode())
        self.nodes[os.path.join(parent, name)] = node
        self.nodes[parent].children[name] = node

    def mkfile(self, rel, data=b"0123456789", inode=None, mtime_ns=-10**18):
        parent, name = self._parts(rel)
        node = _Node(False, mtime_ns,
                     inode if inode is not None else self._inode(), data)
        self.nodes[os.path.join(parent, name)] = node
        self.nodes[parent].children[name] = node
        return node

    def write(self, rel, data):
        node = self.nodes[os.path.join(self.root, rel)]
        node.data, node.size = data, len(data)

    def remove(self, rel):
        parent, name = self._parts(rel)
        path = os.path.join(parent, name)
        del self.nodes[parent].children[name]
        del self.nodes[path]

    def last_inode_of(self, rel):
        return self.nodes[os.path.join(self.root, rel)].inode

    def stat(self, path):
        node = self.nodes.get(path)
        if node is None:
            raise FileNotFoundError(path)
        return StatEntry(node.mtime_ns, node.size, node.inode, node.is_dir)

    def scandir(self, path):
        node = self.nodes.get(path)
        if node is None:
            raise FileNotFoundError(path)
        if not node.is_dir:
            raise NotADirectoryError(path)
        return sorted(node.children)

    def read_bytes(self, path):
        self.reads += 1
        node = self.nodes.get(path)
        if node is None:
            raise FileNotFoundError(path)
        return node.data


class TestBatchOrdering(unittest.TestCase):
    def test_order_is_deleted_modified_moved_created_by_depth(self):
        fs = _MemoryFS()
        fs.mkdir("d")
        fs.mkfile("keep1.txt")
        fs.mkfile("d/keep2.txt")
        fs.mkfile("d/gone.txt")
        fs.mkfile("rename.txt")
        fs.mkfile("d/edit.txt")
        clock = ManualClock(0.0)
        watcher = Watcher("/root", fs=fs, clock=clock)
        drain(watcher, clock)
        inode = fs.last_inode_of("rename.txt")
        fs.remove("d/gone.txt")
        fs.remove("rename.txt")
        fs.mkfile("rename-dest.txt", inode=inode)
        fs.write("d/edit.txt", b"brand-new-content-here")
        fs.mkdir("newdir")
        fs.mkfile("newdir/child.txt")
        fs.mkfile("top-new.txt")
        events = drain(watcher, clock)
        self.assertEqual(
            [(event.kind, event.path, event.dest) for event in events],
            [(DELETED, "d/gone.txt", None),
             (MODIFIED, "d/edit.txt", None),
             (MOVED, "rename.txt", "rename-dest.txt"),
             (CREATED, "newdir", None),
             (CREATED, "top-new.txt", None),
             (CREATED, "newdir/child.txt", None)])


class TestRenameChains(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.clock = ManualClock(1000.0)

    def test_two_hop_rename_during_debounce_is_one_moved(self):
        path = make_file(self.root, "a.txt", b"x", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        drain(watcher, self.clock)
        os.rename(path, os.path.join(self.root, "b.txt"))
        self.clock.advance(0.1)
        self.assertEqual(watcher.poll(), [])
        os.rename(os.path.join(self.root, "b.txt"),
                  os.path.join(self.root, "c.txt"))
        self.clock.advance(0.1)
        self.assertEqual(watcher.poll(), [])
        self.clock.advance(1.0)
        self.assertEqual(watcher.poll(),
                         [Event(MOVED, "a.txt", False, "c.txt")])


class TestStaticTreeReadsNothing(unittest.TestCase):
    def test_real_fs_idle_scan_does_not_read(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(1000.0)
            for index in range(20):
                make_file(root, "d/f%02d.txt" % index, b"data" * 8, clock,
                          stamp=0.0)
            fs = ReadCountingFS()
            watcher = Watcher(root, fs=fs, clock=clock)
            before = fs.reads
            clock.advance(10.0)
            self.assertEqual(watcher.poll(), [])
            self.assertEqual(fs.reads, before)
            make_file(root, "d/f00.txt", b"different!" * 4, clock)
            clock.advance(10.0)
            self.assertEqual(watcher.poll(), [])
            clock.advance(1.0)
            events = watcher.poll()
            self.assertEqual(events, [Event(MODIFIED, "d/f00.txt", False)])
            self.assertGreaterEqual(fs.reads, before + 1)

    def test_hundred_thousand_entries_scan_fast_without_reads(self):
        fs = _MemoryFS()
        dir_count, per_dir = 100, 1000
        for dir_index in range(dir_count):
            rel = "d%03d" % dir_index
            fs.mkdir(rel)
            for file_index in range(per_dir):
                fs.mkfile("%s/f%04d.txt" % (rel, file_index))
        self.assertEqual(len(fs.nodes) - 1, dir_count * (per_dir + 1))
        clock = ManualClock(0.0)
        start = time.perf_counter()
        watcher = Watcher("/root", fs=fs, clock=clock)
        events = watcher.poll()
        elapsed = time.perf_counter() - start
        self.assertEqual(events, [])
        self.assertEqual(fs.reads, 0)
        self.assertLess(elapsed, 5.0)
        self.assertEqual(len(watcher.snapshot()), dir_count * (per_dir + 1))


class TestReferenceAlignment(unittest.TestCase):
    """随机操作序列配随机扫描时机，事件集合与顺序都要和基准一致。"""

    def _run(self, seed, granularity, gap_high, rounds=70):
        with tempfile.TemporaryDirectory() as root:
            rng = random.Random(seed * 104729 + 7)
            clock = ManualClock(1000.0)
            script = OpScript(root, clock, granularity=granularity, seed=seed)
            initial = script.setup()
            watcher = Watcher(root, fs=SysFS(), clock=clock)
            oracle = OpReference(debounce=watcher.debounce)
            oracle.prime(initial)
            got, want = [], []
            for _ in range(rounds):
                ops = script.step(n_ops=rng.randrange(0, 4))
                clock.advance(rng.uniform(0.0, gap_high))
                want.extend(oracle.feed(clock(), ops))
                got.extend(watcher.poll())
            for _ in range(8):
                clock.advance(1.0)
                want.extend(oracle.feed(clock(), []))
                got.extend(watcher.poll())
            return got, want

    def test_random_operations_match_reference(self):
        scenarios = [
            (1, 1.0, 0.45), (2, 1.0, 0.1), (3, 1.0, 4.0),
            (4, 2.0, 2.0), (5, 0.5, 0.6), (6, 1.0, 0.02),
            (7, 1.0, 1.5), (8, 3.0, 3.0),
        ]
        for seed, granularity, gap_high in scenarios:
            with self.subTest(seed=seed, granularity=granularity,
                              gap=gap_high):
                got, want = self._run(seed, granularity, gap_high)
                if got != want:
                    for index, (actual, expected) in enumerate(
                            zip(got, want)):
                        if actual != expected:
                            self.fail(
                                "seed=%s 第 %d 条不一致：%r != %r"
                                % (seed, index, actual, expected))
                    self.fail("seed=%s 事件数不一致：%d != %d"
                              % (seed, len(got), len(want)))


if __name__ == "__main__":
    unittest.main()
