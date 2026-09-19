"""单机 KV 存储，JSON 行 append 日志持久化 + MVCC 事务。

每次 put/delete 追加一条 JSON 记录，重启时按文件序重放恢复。
MVCC：begin() 开事务，get 读 begin 时刻快照，put/delete 先落缓冲；
commit 按写集做 first-committer-wins 检测，冲突抛 ConflictError。
不带事务的 get/put/delete 保持原语义，相当于自动提交的单操作事务。
"""

import json
import os
import threading

_TOMBSTONE = object()


class ConflictError(Exception):
    """commit 时写集中的 key 在快照之后被其他事务提交过。"""


class Transaction:
    """MVCC 事务：读 begin 时刻快照，写先进缓冲，commit 时冲突检测。"""

    def __init__(self, store, snapshot_version):
        self._store = store
        self._snapshot = snapshot_version
        self._writes = {}
        self._active = True

    @property
    def snapshot_version(self):
        return self._snapshot

    def _check_active(self):
        if not self._active:
            raise RuntimeError("transaction is no longer active")

    def get(self, key):
        self._check_active()
        if key in self._writes:
            value = self._writes[key]
            return None if value is _TOMBSTONE else value
        with self._store._lock:
            return self._store._read_at(key, self._snapshot)

    def put(self, key, value):
        self._check_active()
        self._writes[key] = value

    def delete(self, key):
        self._check_active()
        existed = self.get(key) is not None
        self._writes[key] = _TOMBSTONE
        return existed

    def commit(self):
        self._check_active()
        try:
            self._store._commit(self)
        finally:
            self._active = False
            self._store._unregister(self)

    def rollback(self):
        self._check_active()
        self._writes.clear()
        self._active = False
        self._store._unregister(self)


class Store:
    """单机 KV。

    path 为空时纯内存；给了 path 则所有写操作追加一份 JSON 行日志，
    重新打开同一 path 即恢复到最近状态。value 须可 JSON 序列化。
    """

    def __init__(self, path=None):
        self._lock = threading.Lock()
        self._versions = {}      # key -> [(version, value|_TOMBSTONE)] 按版本升序
        self._key_version = {}   # key -> 最后提交版本（gc 不清理，用于冲突判定）
        self._version = 0        # 全局版本号，每次成功提交加一
        self._active_txns = set()
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
                self._version += 1
                if rec["op"] == "put":
                    self._apply(rec["key"], rec["value"], self._version)
                elif rec["op"] == "del":
                    self._apply(rec["key"], _TOMBSTONE, self._version)

    def _append(self, record):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")

    def _apply(self, key, value, version):
        self._versions.setdefault(key, []).append((version, value))
        self._key_version[key] = version

    def _read_at(self, key, snapshot):
        versions = self._versions.get(key)
        if not versions:
            return None
        for version, value in reversed(versions):
            if version <= snapshot:
                return None if value is _TOMBSTONE else value
        return None

    def get(self, key):
        with self._lock:
            return self._read_at(key, self._version)

    def put(self, key, value):
        with self._lock:
            self._version += 1
            self._apply(key, value, self._version)
        if self._path is not None:
            self._append({"op": "put", "key": key, "value": value})

    def delete(self, key):
        with self._lock:
            existed = self._read_at(key, self._version) is not None
            if existed:
                self._version += 1
                self._apply(key, _TOMBSTONE, self._version)
        if existed and self._path is not None:
            self._append({"op": "del", "key": key})
        return existed

    def begin(self):
        """开事务，快照为当前全局版本号。"""
        with self._lock:
            tx = Transaction(self, self._version)
            self._active_txns.add(tx)
            return tx

    def _commit(self, tx):
        with self._lock:
            for key in tx._writes:
                if self._key_version.get(key, 0) > tx._snapshot:
                    raise ConflictError(
                        "key %r modified after snapshot (first-committer-wins)" % key
                    )
            self._version += 1
            version = self._version
            for key, value in tx._writes.items():
                self._apply(key, value, version)
        if self._path is not None:
            for key, value in tx._writes.items():
                if value is _TOMBSTONE:
                    self._append({"op": "del", "key": key})
                else:
                    self._append({"op": "put", "key": key, "value": value})

    def _unregister(self, tx):
        with self._lock:
            self._active_txns.discard(tx)

    def gc(self):
        """回收活跃事务快照不再引用的旧版本；无活跃事务时每 key 只留最新版。"""
        with self._lock:
            snapshots = [tx._snapshot for tx in self._active_txns]
            for key in list(self._versions):
                versions = self._versions[key]
                keep = {versions[-1][0]}
                for snapshot in snapshots:
                    for version, _ in reversed(versions):
                        if version <= snapshot:
                            keep.add(version)
                            break
                self._versions[key] = [e for e in versions if e[0] in keep]
