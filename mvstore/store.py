"""单机 KV 存储，JSON 行 append 日志持久化，内置 MVCC 事务。

每次提交的 put/delete 追加一条 JSON 记录，重启时按文件序重放恢复。
事务通过 begin() 开启：get 读 begin 时刻快照，put/delete 先落缓冲，
commit 按写集做 first-committer-wins 冲突检测，rollback 丢弃缓冲。
"""

import json
import os
import threading


class ConflictError(Exception):
    """提交时发现写集 key 在快照之后被别的事务提交过。"""


class Transaction:
    """Store.begin() 返回的事务句柄。

    每个事务持有 begin 时刻的全局版本作为只读快照，put/delete
    缓存在本地直到 commit；commit/rollback 后事务即作废。
    """

    def __init__(self, store, snapshot_version):
        self._store = store
        self._snapshot_version = snapshot_version
        self._buffer = {}
        self._finished = False

    def _check_open(self):
        if self._finished:
            raise RuntimeError("transaction already committed or rolled back")

    @property
    def snapshot_version(self):
        return self._snapshot_version

    def get(self, key):
        self._check_open()
        if key in self._buffer:
            return self._buffer[key]
        return self._store._snapshot_read(key, self._snapshot_version)

    def put(self, key, value):
        self._check_open()
        self._buffer[key] = value

    def delete(self, key):
        self._check_open()
        existed = self.get(key) is not None
        self._buffer[key] = None
        return existed

    def commit(self):
        self._check_open()
        try:
            self._store._commit(self)
        finally:
            self._finished = True

    def rollback(self):
        self._check_open()
        self._store._rollback(self)
        self._finished = True
        self._buffer = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self._finished:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        return False


class Store:
    """单机 KV。

    path 为空时纯内存；给了 path 则所有写操作追加一份 JSON 行日志，
    重新打开同一 path 即恢复到最近状态。value 须可 JSON 序列化。

    begin() 返回 Transaction，提供快照隔离事务与 first-committer-wins
    冲突检测；顶层 get/put/delete 保持无事务自动提交语义不变。
    """

    def __init__(self, path=None):
        self._lock = threading.Lock()
        self._data = {}
        # key -> [{"version": int, "value": object(None 为删除墓碑)}, ...]，版本升序
        self._history = {}
        # key -> 最后一次写入该 key 的提交版本
        self._last_commit_version = {}
        self._global_version = 0
        self._active = set()
        self._path = path
        if path is not None:
            self._replay()
            self.gc()

    def _replay(self):
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("version") is not None:
                    version = rec["version"]
                else:
                    version = self._global_version + 1
                if rec["op"] == "put":
                    self._install_locked(rec["key"], rec["value"], version)
                elif rec["op"] == "del":
                    self._install_locked(rec["key"], None, version)
                self._global_version = max(self._global_version, version)

    def _append(self, record):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")

    # ---- 内部 MVCC 原语（调用方均持有 self._lock，除 _snapshot_read）----

    def _install_locked(self, key, value, version):
        """把一个已提交版本写入内存结构（value=None 表示删除）。"""
        entries = self._history.setdefault(key, [])
        if entries and entries[-1]["version"] >= version:
            return
        entries.append({"version": version, "value": value})
        self._last_commit_version[key] = version
        if value is None:
            self._data.pop(key, None)
        else:
            self._data[key] = value

    def _snapshot_read(self, key, snapshot_version):
        with self._lock:
            value = None
            for entry in self._history.get(key, ()):
                if entry["version"] <= snapshot_version:
                    value = entry["value"]
                else:
                    break
            return value

    def _commit(self, tx):
        with self._lock:
            conflicted = [
                key
                for key in tx._buffer
                if self._last_commit_version.get(key, 0) > tx._snapshot_version
            ]
            if conflicted:
                self._active.discard(tx)
                raise ConflictError(
                    "write conflict on keys: %s"
                    % ", ".join(sorted(str(k) for k in conflicted))
                )
            new_version = self._global_version + 1
            records = []
            for key, value in tx._buffer.items():
                rec = {
                    "version": new_version,
                    "op": "put" if value is not None else "del",
                    "key": key,
                }
                if value is not None:
                    rec["value"] = value
                self._install_locked(key, value, new_version)
                records.append(rec)
            self._global_version = new_version
            self._active.discard(tx)
            if self._path is not None:
                for rec in records:
                    self._append(rec)

    def _rollback(self, tx):
        with self._lock:
            self._active.discard(tx)

    # ---- 事务 API ----

    def begin(self):
        with self._lock:
            tx = Transaction(self, self._global_version)
            self._active.add(tx)
            return tx

    def gc(self):
        """回收活跃事务快照不再引用的旧版本。

        对每个活跃事务的快照版本（以及当前全局版本，供自动提交读），
        找出该快照下每 key 可见的最新版本条目并保留，其余回收；
        无活跃事务时只保留每 key 最新版。key 的最后提交版本元数据
        始终保留。
        """
        with self._lock:
            snapshots = {
                tx._snapshot_version for tx in self._active
            }
            snapshots.add(self._global_version)
            for key, entries in list(self._history.items()):
                keep = set()
                for snapshot_version in snapshots:
                    idx = -1
                    for i, entry in enumerate(entries):
                        if entry["version"] <= snapshot_version:
                            idx = i
                        else:
                            break
                    if idx >= 0:
                        keep.add(idx)
                self._history[key] = [entries[i] for i in sorted(keep)]

    # ---- 顶层无事务 API（自动提交，保持基线语义）----

    def get(self, key):
        return self._snapshot_read(key, self._global_version)

    def put(self, key, value):
        with self._lock:
            version = self._global_version + 1
            self._install_locked(key, value, version)
            self._global_version = version
            if self._path is not None:
                self._append({"op": "put", "key": key, "value": value})

    def delete(self, key):
        with self._lock:
            entries = self._history.get(key)
            existed = bool(entries and entries[-1]["value"] is not None)
            if existed:
                version = self._global_version + 1
                self._install_locked(key, None, version)
                self._global_version = version
                if self._path is not None:
                    self._append({"op": "del", "key": key})
            return existed
