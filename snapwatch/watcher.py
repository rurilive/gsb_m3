"""Watcher：轮询扫描，按状态机把净变化 debounce 后整批发布。

发布语义和 snapwatch/reference.py 里的 OpReference 完全对齐：同一路径的
连续变化合并成净效果；变化静默 debounce 秒后才发布；同一 inode 的旧路径
消失、新路径出现配成一条 moved；批内顺序是删除（深的在前）、modified、
moved、created（浅的在前），同类按路径排。
"""

import os
import threading
import time

from .fs import SysFS
from .scanner import PollScanner

CREATED = "created"
MODIFIED = "modified"
DELETED = "deleted"
MOVED = "moved"


_RANK = {DELETED: 0, MODIFIED: 1, MOVED: 2, CREATED: 3}


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


def _sort_key(event):
    """批内顺序，和 reference.sort_key 保持一致。"""
    depth = event.path.count("/") + 1
    if event.kind == DELETED:
        depth = -depth
    return (_RANK[event.kind], depth, event.path)


def _publish(pairs):
    """把 (路径, 旧状态, 新状态) 收成一批排好序的事件，和 reference.publish 一致。"""
    events, created_at, deleted_at = [], {}, {}
    for path, old, new in pairs:
        if old is None:
            created_at[new[3]] = len(events)
            events.append(Event(CREATED, path, new[0]))
        elif new is None:
            deleted_at[old[3]] = len(events)
            events.append(Event(DELETED, path, old[0]))
        elif old != new:
            events.append(Event(MODIFIED, path, new[0]))
    dropped = set()
    for inode, index in deleted_at.items():
        mate = created_at.get(inode)
        if mate is not None and mate not in dropped:
            events[index] = Event(MOVED, events[index].path,
                                  events[index].is_dir, events[mate].path)
            dropped.add(mate)
    events = [event for index, event in enumerate(events)
              if index not in dropped]
    events.sort(key=_sort_key)
    return events


class Watcher:
    """盯住一棵目录树，poll() 取一批事件，subscribe() 挂回调。"""

    def __init__(self, root, fs=None, clock=time.time, interval=0.5,
                 debounce=0.25, granularity=1.0):
        self.fs = fs if fs is not None else SysFS()
        self.root = os.path.abspath(root)
        self.clock = clock
        self.interval = interval
        self.debounce = float(debounce)
        # 文件系统时间戳精度（秒）。mtime 所在时间片还没走完时，同一片内
        # 的再写不会改变 mtime，只能靠内容 digest 分辨，所以这段时间内的
        # 文件每次都要重读；时间片走完后最后确认一次，之后静止不再读。
        self.granularity_ns = max(1, int(float(granularity) * 1e9))
        self.last_poll_at = None
        self._scanner = PollScanner(self.fs, self.root)
        self._callbacks, self._thread = [], None
        self._stopped = threading.Event()
        self._committed = {}
        self._observed = {}
        self._pending = {}
        self._confirmed = set()
        self._snapshot = self._scanner.scan()
        self._prime(self.clock())

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
        states = {}
        for path, entry in fresh.entries.items():
            try:
                states[path] = self._state_of(path, entry, now)
            except OSError:
                # 扫描和读取之间文件没了，沿用旧状态，下一轮再说
                previous = self._observed.get(path)
                if previous is not None:
                    states[path] = previous
        # 扫不出来的目录（比如被 chmod）不等于子树被删，沿用上一轮状态
        for rel in fresh.failed:
            prefix = rel + "/" if rel else ""
            for path, state in self._observed.items():
                if state is not None and path.startswith(prefix):
                    states[path] = state
        events = self._advance(now, states)
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

    def _prime(self, now):
        """打底：把存量树的状态当作已经发布过的东西。"""
        for path, entry in self._snapshot.entries.items():
            state = self._state_of(path, entry, now)
            self._observed[path] = state
            self._committed[path] = state

    def _slice_closed(self, mtime_ns, now):
        """mtime 所在的时间片是否已经走完，走完则同片再写不可能。"""
        now_ns = int(now * 1e9)
        end = mtime_ns // self.granularity_ns * self.granularity_ns
        return end + self.granularity_ns <= now_ns

    def _state_of(self, path, entry, now):
        """路径当前的可观测状态 (is_dir, size, mtime_ns, inode, digest)。"""
        meta = (entry.is_dir, entry.size, entry.mtime_ns, entry.inode)
        if entry.is_dir:
            return meta + (None,)
        previous = self._observed.get(path)
        if previous is not None and previous[:4] == meta:
            if path in self._confirmed:
                # 时间片早已走完，内容不可能再变，静止时不重读
                return previous
            # 时间片没走完时同片再写不改 mtime，只能靠 digest 分辨；
            # 片走完后做最后一次确认读
            digest = entry.digest
            if self._slice_closed(entry.mtime_ns, now):
                self._confirmed.add(path)
            return meta + (digest,)
        if self._slice_closed(entry.mtime_ns, now):
            # 时间片已走完的新路径，内容不可能再变，digest 用不到就不读
            self._confirmed.add(path)
            return meta + (None,)
        self._confirmed.discard(path)
        return meta + (entry.digest,)

    def _advance(self, now, states):
        """和 OpReference.feed 同构：更新观测，发布静默够久的净变化。"""
        for path, state in self._observed.items():
            if state is not None and path not in states:
                states[path] = None
        for path, state in states.items():
            if state == self._observed.get(path):
                continue
            self._observed[path] = state
            if state is None:
                self._confirmed.discard(path)
            if state == self._committed.get(path):
                self._pending.pop(path, None)
            else:
                self._pending[path] = (now, state)
        ready = [(path, state) for path, (at, state) in self._pending.items()
                 if now - at >= self.debounce]
        pairs = []
        for path, state in ready:
            del self._pending[path]
            pairs.append((path, self._committed.get(path), state))
            self._committed[path] = state
        return _publish(pairs)
