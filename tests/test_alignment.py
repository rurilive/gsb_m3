"""Watcher 与 OpReference 的对拍测试，外加四类现场的回归。

对拍：OpScript 在真实目录上做随机操作，扫描时机也随机，每一轮
watcher.poll() 的事件必须和 OpReference.feed() 算出的基准完全相等
（集合与顺序都算上）。
"""

import os
import tempfile
import unittest

from snapwatch import (Event, ManualClock, OpReference, OpScript, SysFS,
                       Watcher)


def align(seed, rounds=60, granularity=1.0):
    """跑一条随机操作序列，对拍失败时抛 AssertionError。"""
    tmp = tempfile.TemporaryDirectory()
    clock = ManualClock(1000.0)
    script = OpScript(tmp.name, clock, granularity=granularity, seed=seed)
    reference = OpReference()
    reference.prime(script.setup())
    watcher = Watcher(tmp.name, fs=SysFS(), clock=clock,
                      granularity=granularity)
    for _ in range(rounds):
        ops = script.step(n_ops=script.rng.randrange(1, 4))
        clock.advance(script.rng.uniform(0.0, 0.5))
        expected = reference.feed(clock(), ops)
        actual = watcher.poll()
        if actual != expected:
            tmp.cleanup()
            raise AssertionError(
                "seed=%d 对拍失败\n期望：%r\n实际：%r" % (seed, expected, actual))
    return tmp


class TestAlignment(unittest.TestCase):
    def test_random_sequences_match_reference(self):
        for seed in (1, 2, 3, 7, 42, 99):
            align(seed).cleanup()

    def test_coarse_granularity_matches_reference(self):
        align(5, granularity=2.0).cleanup()


def make_file(root, rel, data, clock, stamp=None):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    value = int((clock() if stamp is None else stamp) * 1e9)
    os.utime(path, ns=(value, value))
    return path


class RegressionBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.clock = ManualClock(1000.0)

    def collect(self, watcher, rounds=4, step=1.0):
        events = []
        for _ in range(rounds):
            self.clock.advance(step)
            events.extend(watcher.poll())
        return events


class TestAtomicSave(RegressionBase):
    def test_replace_reports_single_modified(self):
        make_file(self.root, "notes.txt", b"v1", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        self.collect(watcher)
        self.clock.advance(1.0)
        tmp = make_file(self.root, "notes.txt.tmp", b"v2", self.clock)
        os.replace(tmp, os.path.join(self.root, "notes.txt"))
        self.assertEqual(self.collect(watcher),
                         [Event("modified", "notes.txt", False)])


class TestSaveStorm(RegressionBase):
    def test_burst_of_writes_collapses_to_one_event(self):
        make_file(self.root, "notes.txt", b"v1", self.clock)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        self.collect(watcher)
        events = []
        for content in (b"v2", b"v3", b"v4"):
            self.clock.advance(0.4)
            make_file(self.root, "notes.txt", content, self.clock)
            events.extend(watcher.poll())
        events.extend(self.collect(watcher))
        self.assertEqual(events, [Event("modified", "notes.txt", False)])


class TestCoarseTimestamps(RegressionBase):
    def test_same_second_same_size_second_write_is_seen(self):
        make_file(self.root, "build.log", b"aaaaaaaa", self.clock, stamp=1000.0)
        watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)
        self.collect(watcher, rounds=2, step=0.2)
        for content in (b"bbbbbbbb", b"cccccccc"):
            self.clock.advance(0.2)
            make_file(self.root, "build.log", content, self.clock,
                      stamp=1000.0)
        self.assertEqual(self.collect(watcher, step=0.2),
                         [Event("modified", "build.log", False)])


class CountingFS(SysFS):
    """数 read_bytes 调了多少次的文件系统替身。"""

    def __init__(self):
        self.reads = 0

    def read_bytes(self, path):
        self.reads += 1
        return super().read_bytes(path)


class TestIdleScanDoesNotRead(RegressionBase):
    def test_quiet_tree_is_not_reread(self):
        for index in range(50):
            make_file(self.root, "f%02d.txt" % index, b"data", self.clock)
        filesystem = CountingFS()
        watcher = Watcher(self.root, fs=filesystem, clock=self.clock)
        self.collect(watcher)  # 时间片走完，确认读都发生在这里
        filesystem.reads = 0
        self.assertEqual(self.collect(watcher), [])
        self.assertEqual(filesystem.reads, 0)


class BlockedFS(SysFS):
    """模拟被监听目录被 chmod：scandir 抛权限错误。"""

    def __init__(self, name):
        self.name = name
        self.blocked = False

    def scandir(self, path):
        if self.blocked and path.endswith(os.sep + self.name):
            raise PermissionError(path)
        return super().scandir(path)


class TestBlockedDirectory(RegressionBase):
    def test_chmodded_subtree_is_not_reported_deleted(self):
        for name in ("f1.txt", "f2.txt", "f3.txt"):
            make_file(self.root, "d0/" + name, b"x", self.clock)
        filesystem = BlockedFS("d0")
        watcher = Watcher(self.root, fs=filesystem, clock=self.clock)
        self.collect(watcher)
        filesystem.blocked = True
        self.assertEqual(self.collect(watcher), [])
        # 恢复之后也不该冒出补报的事件
        filesystem.blocked = False
        self.assertEqual(self.collect(watcher), [])


if __name__ == "__main__":
    unittest.main()
