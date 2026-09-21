"""Watcher：轮询扫描，按静默 debounce 发布净效果事件。"""

import os
import threading
import time

from .fs import SysFS
from .scanner import PollScanner

CREATED = "created"
MODIFIED = "modified"
DELETED = "deleted"
MOVED = "moved"


class Event:
    """一条变化事件。moved 的 path 是旧路径，dest 是新路径。"""

    __slots__ = ("kind", "path", "dest", "is_dir")

    def __init__(self, kind, path, is_dir=False, dest=None):
        self.kind = kind
        self.path = path
        self.is_dir = is_dir
        self.dest = dest

    def __eq__(self, other):
        return (self.kind, self.path, self.dest, self.is_dir) == (
            other.kind, other.path, other.dest, other.is_dir)

    def __hash__(self):
        return hash((self.kind, self.path, self.dest, self.is_dir))

    def __repr__(self):
        if self.kind == MOVED:
            return "Event(moved %r -> %r)" % (self.path, self.dest)
        return "Event(%s %r)" % (self.kind, self.path)


class Watcher:
    """盯住一棵目录树，poll() 取一批事件，subscribe() 挂回调。"""

    def __init__(self, root, fs=None, clock=time.time, interval=0.5,
                 debounce=0.25, timestamp_granularity=1.0):
        """debounce 是静默秒数；timestamp_granularity 是盘上 mtime 的
        最小时间片（秒），同一时间片内只改内容时靠读 digest 兜底；
        设成 0 表示只信元数据，永不因为时间片而读内容。"""
        self.fs = fs if fs is not None else SysFS()
        self.root = os.path.abspath(root)
        self.clock = clock
        self.interval = interval
        self.debounce = float(debounce)
        self.granularity_ns = int(float(timestamp_granularity) * 1e9)
        self.last_poll_at = None
        self._scanner = PollScanner(self.fs, self.root)
        self._snapshot = self._scanner.scan()
        self._committed = {}
        self._observed = {}
        self._pending = {}
        self._prime_states()
        self._callbacks, self._thread = [], None
        self._stopped = threading.Event()

    def snapshot(self):
        """最近一次扫描的快照。"""
        return self._snapshot

    def subscribe(self, callback):
        """挂一个回调，事件按批内顺序逐个喂进去。"""
        self._callbacks.append(callback)

    def poll(self):
        """再扫一遍，返回这批事件，同时喂给回调。"""
        now = self.clock()
        self.last_poll_at = now
        fresh = self._scanner.scan()
        events = self._advance(self._snapshot, fresh, now)
        self._snapshot = fresh
        for event in events:
            for callback in self._callbacks:
                callback(event)
        return events

    def start(self):
        """起一个后台线程按 interval 反复 poll。"""
        if self._thread is not None:
            return
        self._stopped.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停掉后台线程，可以重复调。"""
        self._stopped.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=self.interval + 1.0)

    def _loop(self):
        while not self._stopped.is_set():
            self.poll()
            self._stopped.wait(self.interval)

    def _prime_states(self):
        """打底：存量树当作已发布。落在当前热时间片里的文件读一次
        digest，防止打底后同时间片内只改内容、长度也没变。"""
        now_ns = int(self.clock() * 1e9)
        edge = (now_ns - now_ns % self.granularity_ns
                if self.granularity_ns else now_ns + 1)
        states = {}
        for path, entry in self._snapshot.entries.items():
            if entry.is_dir:
                digest = None
            elif entry.mtime_ns >= edge:
                digest = self._digest(entry)
            else:
                digest = None
            entry._digest = digest
            states[path] = self._state_of(entry)
        self._committed = states
        self._observed = dict(states)

    def _state_of(self, entry):
        digest = self._digest(entry) if entry._digest is not None else None
        return (entry.is_dir, entry.size, entry.mtime_ns, entry.inode,
                digest)

    @staticmethod
    def _digest(entry):
        try:
            return entry.digest
        except OSError:
            return None

    def _in_hot_slice(self, mtime_ns, now):
        if not self.granularity_ns:
            return False
        now_ns = int(now * 1e9)
        edge = now_ns - now_ns % self.granularity_ns
        return mtime_ns >= edge

    def _gather(self, prev, fresh, now):
        """本轮每个可判定路径的净状态：present 是五元组，缺失是 None。
        读不出来的子树沿用上一轮的判定，不当成删除。"""
        result = {}
        for path, entry in fresh.entries.items():
            old = prev.entries.get(path)
            previous = self._observed.get(path)
            if entry.is_dir:
                entry._digest = None
            else:
                metadata_changed = old is None or (
                    old.is_dir, old.size, old.mtime_ns, old.inode) != (
                        entry.is_dir, entry.size, entry.mtime_ns,
                        entry.inode)
                if metadata_changed:
                    self._digest(entry)
                elif self._in_hot_slice(entry.mtime_ns, now):
                    self._digest(entry)
                elif (previous is not None
                      and previous[4] is not None
                      and (previous[0], previous[1], previous[2],
                           previous[3])
                      == (entry.is_dir, entry.size, entry.mtime_ns,
                          entry.inode)):
                    entry._digest = previous[4]
                else:
                    entry._digest = None
            result[path] = self._state_of(entry)
        for path, old in prev.entries.items():
            if path in result:
                continue
            if fresh.is_unreachable(path):
                result[path] = self._observed.get(
                    path, self._state_of(old))
            else:
                result[path] = None
        return result

    def _advance(self, prev, fresh, now):
        final = self._gather(prev, fresh, now)
        for path, state in final.items():
            if state == self._observed.get(path):
                continue
            self._observed[path] = state
            if state == self._committed.get(path):
                self._pending.pop(path, None)
            else:
                self._pending[path] = (now, state)
        ready = [(path, state) for path, (at, state)
                 in self._pending.items() if now - at >= self.debounce]
        if not ready:
            return []
        pairs = []
        for path, state in ready:
            del self._pending[path]
            pairs.append((path, self._committed.get(path), state))
            self._committed[path] = state
        from .reference import publish
        return publish(pairs)
