"""Watcher：轮询扫描，比对前后两份状态，按 debounce 净效果发布事件。

事件语义和 snapwatch.reference 的对拍基准一致：

- 同一路径一轮里的多次变化合并成净效果；出现又消失的路径不报；
- 变化静默 debounce 秒之后才发布，静默期内又变就重新计时，变回已发布
  的状态时取消挂起；
- 同一个 inode 从旧路径消失、在新路径出现，两条又都在同一轮发布、且新
  路径原本不存在时配成一条 moved；新路径原本就在（原子替换盖到已有文件）
  按 modified 算；
- 批内顺序是 deleted（深的在前）、modified、moved、created（浅的在前），
  同类按路径排；
- mtime 只有秒级精度时，同秒改写且长度不变也能靠内容摘要兜住；静止树
  扫描不读文件内容，只对需要确认的节点算 digest。
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
                 debounce=0.25, resolution=1.0):
        self.fs = fs if fs is not None else SysFS()
        self.root = os.path.abspath(root)
        self.clock = clock
        self.interval = interval
        self.debounce = float(debounce)
        self.resolution_ns = int(float(resolution) * 1e9)
        self.last_poll_at = None
        self._scanner = PollScanner(self.fs, self.root)
        self._snapshot = self._scanner.scan()
        self._observed = {}
        self._committed = {}
        self._pending = {}
        self._prime(self._snapshot)
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
        fresh_paths = self._is_fresh(fresh, int(now * 1e9))
        states = self._collect_states(fresh, force_digest=fresh_paths)
        events = self._reconcile(now, states)
        self._snapshot = fresh
        self._observed = states
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

    def _prime(self, snapshot):
        """打底：存量树当作已经发布过。只对仍在精度窗口内的节点算摘要。"""
        now_ns = self._now_ns()
        states = self._collect_states(
            snapshot, force_digest=self._is_fresh(snapshot, now_ns),
            priming=True)
        self._observed = dict(states)
        self._committed = dict(states)

    def _now_ns(self):
        return int(self.clock() * 1e9)

    def _is_fresh(self, snapshot, now_ns):
        """仍在时间戳精度窗口内、可能同片再写的节点集合。"""
        return {path for path, entry in snapshot.entries.items()
                if not entry.is_dir
                and now_ns - entry.mtime_ns < self.resolution_ns}

    def _collect_states(self, snapshot, force_digest=(), priming=False):
        """把快照收成 (is_dir, size, mtime_ns, inode, digest) 状态表。

        scandir 不出来的目录整棵子树沿用上一轮观测到的状态，避免权限抖动
        被当成批量删除。
        """
        states = {}
        opaque = snapshot.unlisted
        carried = {path for path in self._observed
                   if self._under_opaque(path, opaque)}
        for path in carried:
            states[path] = self._observed[path]
        for path, entry in snapshot.entries.items():
            if self._under_opaque(path, opaque):
                continue
            if entry.is_dir:
                digest = None
            else:
                digest = self._digest_for(path, entry, force_digest, priming)
            states[path] = (entry.is_dir, entry.size, entry.mtime_ns,
                            entry.inode, digest)
        return states

    @staticmethod
    def _under_opaque(path, opaque):
        """路径是否处在某个失读目录（含根）的子树里。"""
        if "" in opaque:
            return True
        return any(path == prefix or path.startswith(prefix + "/")
                   for prefix in opaque)

    def _digest_for(self, path, entry, force_digest, priming):
        """决定这个文件这一轮要不要读内容算 sha256。

        静止树一律不读；元数据变了、路径是新出现的、还在时间戳精度窗口
        内，或者上一轮已挂起时才读，用来兜住同秒同长的改写。
        """
        old = self._observed.get(path)
        if old is not None:
            _, old_size, old_mtime, old_inode, old_digest = old
            meta_same = ((old_size, old_mtime, old_inode)
                         == (entry.size, entry.mtime_ns, entry.inode))
            if meta_same and path not in force_digest and path not in self._pending:
                return old_digest
        elif priming and path not in force_digest:
            return None
        return entry.digest

    def _reconcile(self, now, states):
        """合并净效果、推进挂起计时、发布到点的一批事件。"""
        for path in self._observed.keys() | states.keys():
            state = states.get(path)
            if state == self._observed.get(path):
                continue
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
        if not pairs:
            return []
        from .reference import publish
        return publish(pairs)
