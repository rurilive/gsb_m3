"""单机 KV 存储，JSON 行 append 日志持久化，支持 MVCC 事务。

每次 put/delete（含事务提交）追加一条 JSON 记录，重启时按文件序重放恢复。
MVCC：begin() 开事务，事务内 get 读 begin 时刻快照，put/delete 先落缓冲；
commit 按写集做 first-committer-wins 检测，冲突抛 ConflictError；
rollback 丢弃缓冲；gc() 回收活跃事务快照不再引用的旧版本。
"""

import json
import os
import threading

_TOMBSTONE = object()


class ConflictError(Exception):
    """提交时写集与快照之后已提交的写入冲突（first-committer-wins）。"""


class Store:
    """单机 KV。

    path 为空时纯内存；给了 path 则所有写操作追加一份 JSON 行日志，
    重新打开同一 path 即恢复到最近状态。value 须可 JSON 序列化。

    多版本：全局版本号每次成功提交加一，每个 key 记录最后提交版本；
    裸 put/delete 等价于立即提交的独立事务。
    """

    def __init__(self, path=None):
        self._lock = threading.RLock()
        self._data = {}
        self._version = 0
        self._versions = {}     # key -> [(version, value|_TOMBSTONE)] 升序
        self._key_version = {}  # key -> 最后提交版本
        self._snapshots = {}    # 活跃事务快照版本 -> 引用计数
        self._path = path
        if path is not None:
            self._replay()

    def _replay(self):
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec["op"] == "put":
                    self._apply(rec["key"], rec["value"])
                elif rec["op"] == "del":
                    self._apply(rec["key"], _TOMBSTONE)

    def _apply(self, key, value):
        """应用一条已提交的写入并推进版本（须持锁）。"""
        self._version += 1
        if value is _TOMBSTONE:
            self._data.pop(key, None)
        else:
            self._data[key] = value
        self._versions.setdefault(key, []).append((self._version, value))
        self._key_version[key] = self._version

    def _append(self, record):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")

    def get(self, key):
        with self._lock:
            return self._data.get(key)

    def put(self, key, value):
        with self._lock:
            self._apply(key, value)
            if self._path is not None:
                self._append({"op": "put", "key": key, "value": value})

    def delete(self, key):
        with self._lock:
            existed = key in self._data
            if existed:
                self._apply(key, _TOMBSTONE)
                if self._path is not None:
                    self._append({"op": "del", "key": key})
        return existed

    def begin(self):
        """开事务，快照为当前全局版本。"""
        with self._lock:
            self._snapshots[self._version] = self._snapshots.get(self._version, 0) + 1
            return Transaction(self, self._version)

    def _release_snapshot(self, snapshot):
        with self._lock:
            n = self._snapshots.get(snapshot, 0) - 1
            if n > 0:
                self._snapshots[snapshot] = n
            else:
                self._snapshots.pop(snapshot, None)

    def _visible(self, key, snapshot):
        """快照下 key 的可见值（须持锁），不存在返回 None。"""
        result = None
        for version, value in self._versions.get(key, ()):
            if version > snapshot:
                break
            result = None if value is _TOMBSTONE else value
        return result

    def _commit(self, txn):
        with self._lock:
            try:
                for key in txn._buffer:
                    if self._key_version.get(key, 0) > txn._snapshot:
                        raise ConflictError(
                            "key %r 在快照版本 %d 之后已被提交" % (key, txn._snapshot)
                        )
                for key, value in txn._buffer.items():
                    self._apply(key, value)
                    if self._path is not None:
                        if value is _TOMBSTONE:
                            self._append({"op": "del", "key": key})
                        else:
                            self._append({"op": "put", "key": key, "value": value})
            finally:
                txn._active = False
                self._release_snapshot(txn._snapshot)

    def gc(self):
        """回收活跃事务快照不再引用的旧版本；无活跃事务时每 key 只留最新版。"""
        with self._lock:
            active = sorted(self._snapshots)
            for key, versions in list(self._versions.items()):
                if active:
                    visible = [
                        v for s in active
                        for v in (self._visible_version(versions, s),)
                        if v is not None
                    ]
                    floor = min(visible) if visible else versions[-1][0]
                else:
                    floor = versions[-1][0]
                kept = [e for e in versions if e[0] >= floor]
                if not active and kept[-1][1] is _TOMBSTONE:
                    del self._versions[key]
                else:
                    self._versions[key] = kept

    @staticmethod
    def _visible_version(versions, snapshot):
        result = None
        for version, _ in versions:
            if version > snapshot:
                break
            result = version
        return result


class Transaction:
    """MVCC 事务：读 begin 时刻快照，写先落缓冲，commit 时冲突检测。"""

    def __init__(self, store, snapshot):
        self._store = store
        self._snapshot = snapshot
        self._buffer = {}
        self._active = True

    def _check_active(self):
        if not self._active:
            raise RuntimeError("事务已结束")

    def get(self, key):
        self._check_active()
        if key in self._buffer:
            value = self._buffer[key]
            return None if value is _TOMBSTONE else value
        with self._store._lock:
            return self._store._visible(key, self._snapshot)

    def put(self, key, value):
        self._check_active()
        self._buffer[key] = value

    def delete(self, key):
        self._check_active()
        existed = self.get(key) is not None
        self._buffer[key] = _TOMBSTONE
        return existed

    def commit(self):
        self._check_active()
        self._store._commit(self)

    def rollback(self):
        self._check_active()
        self._buffer.clear()
        self._store._release_snapshot(self._snapshot)
        self._active = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._active:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        return False
