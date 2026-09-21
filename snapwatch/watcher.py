"""Watcher：轮询扫描，比对前后两份快照，把差异变成事件。

语义和 snapwatch.reference 的对拍基准一致：

- 同一路径在静默 debounce 秒内的连写合并成一条净效果，静默期里又变了
  就从最后一次变化重新计时；
- 一轮里出现又消失的路径不报，变化在发布前恢复原样的也不报；
- 同一个 inode 从旧路径消失、在新路径出现且新路径原本不存在时，配成
  一条 moved；新路径原本就在（原子改名盖上去）按 modified 算；
- 批内顺序：deleted（深的在前，子先于父）、modified、moved、
  created（浅的在前，父先于子），同类按路径排；
- 读不出来的目录（权限被 chmod 掉之类）沿用上一份快照里的子树，
  不会把没动过的文件误报成删除。

判断文件变没变主要靠 (mtime_ns, size, inode)，只在时间戳还处在
CONTENT_WINDOW_SECONDS 的"精度存疑窗口"里时才读内容比 digest，静止大树
扫描不读任何文件内容。
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

# mtime 落在这个窗口以内的文件，时间戳精度可能不够（秒级盘、同秒连写），
# 必要时读内容比对；窗口外的旧文件只信 (mtime_ns, size, inode)。
CONTENT_WINDOW_SECONDS = 5.0

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


class Watcher:
    """盯住一棵目录树，poll() 取一批事件，subscribe() 挂回调。"""

    def __init__(self, root, fs=None, clock=time.time, interval=0.5,
                 debounce=0.25):
        self.fs = fs if fs is not None else SysFS()
        self.root = os.path.abspath(root)
        self.clock = clock
        self.interval = interval
        self.debounce = float(debounce)
        self.last_poll_at = None
        self._scanner = PollScanner(self.fs, self.root)
        self._snapshot = self._scanner.scan()
        self._window_ns = int(CONTENT_WINDOW_SECONDS * 1e9)
        self._committed = self._prime_states(self._snapshot, self.clock())
        self._observed = dict(self._committed)
        self._pending = {}
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
        self._snapshot = self._effective_snapshot(self._scanner.scan())
        events = self._advance(now)
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

    def _prime_states(self, snapshot, now_ns_clock):
        """打底状态。窗口内的年轻文件把 digest 也算出来，防止构造前的
        同秒改写漏检；老文件只存 (mtime_ns, size, inode)，不读内容。"""
        now_ns = int(now_ns_clock * 1e9)
        states = {}
        for path, entry in snapshot.entries.items():
            digest = None
            if not entry.is_dir and now_ns - entry.mtime_ns < self._window_ns:
                digest = self._safe_digest(entry)
            states[path] = (entry.is_dir, entry.size, entry.mtime_ns,
                            entry.inode, digest)
        return states

    def _effective_snapshot(self, scanned):
        """scandir 失败的 opaque 目录，把子树从上一份快照搬过来。"""
        if not scanned.opaque_dirs:
            return scanned
        retained = dict(scanned.entries)
        if "" in scanned.opaque_dirs:
            scanned.entries = dict(self._snapshot.entries)
            return scanned
        for directory in scanned.opaque_dirs:
            prefix = directory + "/"
            for path, entry in self._snapshot.entries.items():
                if path == directory or path.startswith(prefix):
                    retained.setdefault(path, entry)
        scanned.entries = retained
        return scanned

    def _advance(self, now):
        """镜像 OpReference.feed：更新观测态、登记/撤销待发布，吐出成熟事件。"""
        observed_now = {}
        for path in set(self._observed) | set(self._snapshot.entries):
            entry = self._snapshot.entries.get(path)
            observed_now[path] = (
                None if entry is None else self._state_for(entry, now, path))
        for path, state in observed_now.items():
            if self._same_state(state, self._observed.get(path)):
                continue
            self._observed[path] = state
            if self._same_state(state, self._committed.get(path)):
                self._pending.pop(path, None)
                if state is not None:
                    known = self._committed.get(path)
                    if known is not None and known[4] is None:
                        self._committed[path] = self._merge_state(known, state)
            else:
                self._pending[path] = (now, state)
        pairs = []
        for path, (at, state) in list(self._pending.items()):
            if now - at >= self.debounce:
                del self._pending[path]
                pairs.append((path, self._committed.get(path), state))
                if state is None:
                    self._committed.pop(path, None)
                    self._observed.pop(path, None)
                else:
                    self._committed[path] = state
        return self._publish(pairs)

    def _state_for(self, entry, now, path):
        """把 Entry 变成五元组状态；只有精度存疑时才读内容。"""
        if entry.is_dir:
            return (True, entry.size, entry.mtime_ns, entry.inode, None)
        now_ns = int(now * 1e9)
        cheap = (entry.mtime_ns, entry.size)
        old = self._observed.get(path)
        old_cheap = None if old is None else (old[2], old[1])
        digest = None
        if now_ns - entry.mtime_ns < self._window_ns or cheap != old_cheap:
            digest = self._safe_digest(entry)
        elif old is not None:
            digest = old[4]
        return (False, entry.size, entry.mtime_ns, entry.inode, digest)

    @staticmethod
    def _safe_digest(entry):
        """读内容算 sha256；文件在扫描后消失就算不出来。"""
        try:
            return entry.digest
        except OSError:
            return None

    @staticmethod
    def _same_state(left, right):
        """五元组比较，其中一方 digest 未知（None）时不把它当成差异。"""
        if left is None or right is None:
            return left is right
        if left[:4] != right[:4]:
            return False
        if left[4] is None or right[4] is None:
            return True
        return left[4] == right[4]

    @staticmethod
    def _merge_state(committed, observed):
        """把刚观测到的已知 digest 补进 committed 里的未知槽位。"""
        if committed[4] is not None or observed[4] is None:
            return committed
        return committed[:4] + (observed[4],)

    def _publish(self, pairs):
        """与 reference.publish 同一套配对和排序规则。"""
        events, created_at, deleted_at = [], {}, {}
        for path, old, new in pairs:
            if old is None:
                created_at[new[3]] = len(events)
                events.append(Event(CREATED, path, new[0]))
            elif new is None:
                deleted_at[old[3]] = len(events)
                events.append(Event(DELETED, path, old[0]))
            elif not self._same_state(old, new):
                events.append(Event(MODIFIED, path, new[0]))
        dropped = set()
        for inode, index in deleted_at.items():
            mate = created_at.get(inode)
            if mate is not None and mate not in dropped:
                events[index] = Event(MOVED, events[index].path,
                                      events[index].is_dir,
                                      events[mate].path)
                dropped.add(mate)
        events = [event for index, event in enumerate(events)
                  if index not in dropped]
        events.sort(key=self._sort_key)
        return events

    @staticmethod
    def _sort_key(event):
        depth = event.path.count("/") + 1
        if event.kind == DELETED:
            depth = -depth
        return (_RANK[event.kind], depth, event.path)
