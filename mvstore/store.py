"""单机 KV 存储，JSON 行 append 日志持久化，带 MVCC 事务。

每个 key 维护一条版本链，(version, value) 按版本号降序排列；
value 为内部哨兵 ``_TOMBSTONE`` 表示该版本是一次 delete。全局版本号
``_next_version`` 在每次成功提交（事务提交及单操作自动提交）后加一。

事务 begin 时记下当时的快照版本：get 读该快照，put/delete 先落
写集缓冲；commit 按写集做 first-committer-wins 检测，写集中任一
key 的最后提交版本新于快照版本即抛 :class:`ConflictError` 并作废，
否则整体生效并推进版本。gc 回收所有活跃事务快照都不再需要的旧
版本，无活跃事务时每个 key 只留最新版本。
"""

import json
import os
import threading


class ConflictError(Exception):
    """提交冲突：写集中的 key 自快照以来已被其他事务提交过。"""

    def __init__(self, key, snapshot_version, committed_version):
        self.key = key
        self.snapshot_version = snapshot_version
        self.committed_version = committed_version
        super().__init__(
            "conflict on key %r: snapshot v%d, last commit v%d"
            % (key, snapshot_version, committed_version)
        )


class Store:
    """单机 KV。

    path 为空时纯内存；给了 path 则所有写操作追加一份 JSON 行日志，
    重新打开同一 path 即恢复到最近状态。value 须可 JSON 序列化。
    """

    def __init__(self, path=None):
        self._lock = threading.Lock()
        self._log_lock = threading.Lock()
        # key -> 版本链，元素 [version, value]，version 降序；value 为
        # _TOMBSTONE 表示该版本是一次 delete。
        self._versions = {}
        # key -> 最后一次提交的版本号（含删除）。
        self._last_committed = {}
        self._next_version = 0
        # 活跃事务集合；空集即无活跃快照，gc 可把每 key 收到只剩最新版。
        self._txns = set()
        self._path = path
        if path is not None:
            self._replay()

    @staticmethod
    def _read_at(versions, snapshot_version):
        """返回 key 在 snapshot_version 快照下的值（_TOMBSTONE 视为不存在）。"""
        for ver, value in versions:
            if ver <= snapshot_version:
                return None if value is _TOMBSTONE else value
        return None

    def _replay(self):
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                version = self._next_version
                self._next_version += 1
                value = _TOMBSTONE if rec["op"] == "del" else rec["value"]
                self._versions.setdefault(rec["key"], []).insert(0, [version, value])
                self._last_committed[rec["key"]] = version

    def _append_many(self, records):
        if self._path is None:
            return
        with self._log_lock:
            with open(self._path, "a", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
                    f.write("\n")

    def get(self, key):
        with self._lock:
            return self._read_at(self._versions.get(key, ()), self._next_version - 1)

    def put(self, key, value):
        # 单操作自动提交：无条件生效（last-writer-wins），不参与自我冲突检测。
        with self._lock:
            records = self._apply_writes({key: value})
            self._append_many(records)

    def delete(self, key):
        with self._lock:
            chain = self._versions.get(key)
            existed = bool(chain) and chain[0][1] is not _TOMBSTONE
            if existed:
                records = self._apply_writes({key: _TOMBSTONE})
                self._append_many(records)
        return existed

    def _apply_writes(self, writes):
        """在持锁前提下把写集以一个新版本生效，返回待追加的日志记录。"""
        commit_version = self._next_version
        records = []
        for key, value in writes.items():
            self._versions.setdefault(key, []).insert(0, [commit_version, value])
            self._last_committed[key] = commit_version
            if value is _TOMBSTONE:
                records.append({"op": "del", "key": key})
            else:
                records.append({"op": "put", "key": key, "value": value})
        self._next_version += 1
        return records

    def begin(self):
        with self._lock:
            txn = Transaction(self)
            self._txns.add(txn)
            return txn

    def gc(self):
        """回收活跃事务快照不再引用的旧版本。"""
        with self._lock:
            floor = min((t.snapshot_version for t in self._txns), default=None)
            for key in list(self._versions):
                chain = self._versions[key]
                if floor is None:
                    del chain[1:]
                else:
                    # 保留所有新版本，以及快照 floor 仍能读到的那一条
                    # （版本号可能恰好不落在该 key 上，故须保留首个
                    # ver <= floor 的旧条目）。
                    keep = len(chain)
                    for idx, entry in enumerate(chain):
                        if entry[0] <= floor:
                            keep = idx + 1
                            break
                    del chain[keep:]


_MISSING = object()
_TOMBSTONE = object()


class Transaction:
    """快照隔离事务：get 读 begin 时刻快照，put/delete 缓冲到 commit。"""

    def __init__(self, store):
        self._store = store
        # begin 时的全局已提交版本号；已提交版本取 [0, snapshot_version]。
        self.snapshot_version = store._next_version - 1
        # key -> 缓冲值；_TOMBSTONE 表示缓冲了一次 delete。
        self._writes = {}
        self._active = True

    @property
    def active(self):
        return self._active

    def _check_active(self):
        if not self._active:
            raise RuntimeError("transaction is no longer active")

    def get(self, key, default=_MISSING):
        self._check_active()
        with self._store._lock:
            if key in self._writes:
                value = self._writes[key]
                if value is _TOMBSTONE:
                    return default if default is not _MISSING else None
                return value
            return self._store._read_at(
                self._store._versions.get(key, ()), self.snapshot_version
            )

    def put(self, key, value):
        self._check_active()
        with self._store._lock:
            self._writes[key] = value

    def delete(self, key):
        """缓冲一次 delete，返回快照+缓冲视图上该 key 是否存在。"""
        self._check_active()
        store = self._store
        with store._lock:
            if key in self._writes:
                existed = self._writes[key] is not _TOMBSTONE
            else:
                existed = store._read_at(
                    store._versions.get(key, ()), self.snapshot_version
                ) is not None
            self._writes[key] = _TOMBSTONE
            return existed

    def rollback(self):
        if not self._active:
            return
        with self._store._lock:
            if not self._active:
                return
            self._active = False
            self._store._txns.discard(self)

    def commit(self):
        self._check_active()
        store = self._store
        with store._lock:
            # first-committer-wins：写集 key 在快照之后被提交过即冲突。
            for key in self._writes:
                last = store._last_committed.get(key)
                if last is not None and last > self.snapshot_version:
                    self._active = False
                    store._txns.discard(self)
                    raise ConflictError(key, self.snapshot_version, last)

            records = store._apply_writes(self._writes)
            self._active = False
            store._txns.discard(self)
            # 日志在锁内追加，保证并发提交的日志序与生效序一致。
            store._append_many(records)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.rollback()
        elif self._active:
            self.commit()
        return False
