"""进程内键值存储与事务。

单线程模型：KVStore 持有一张键值表，transaction 通过 begin() 开启。
事务开始时给主表拍一份快照，事务内的读走快照，写入先记在写集合里，
提交时并回主表，回滚时丢弃写集合。每个键带一个版本号，
本来是为了提交时检测并发冲突。
"""


class ConflictError(RuntimeError):
    """提交时检测到键在事务开始后被其他事务改过。"""

    def __init__(self, keys):
        self.keys = list(keys)
        super().__init__("conflict on keys: " + ", ".join(repr(k) for k in self.keys))


class KVStore:
    """内存键值表。"""

    def __init__(self, initial=None):
        self._data = dict(initial or {})
        self._versions = {key: 1 for key in self._data}
        self._seq = 1

    def set(self, key, value):
        """写入或覆盖一个键。"""
        self._data[key] = value
        self._bump(key)

    def get(self, key, default=None):
        """读取一个键，不存在时返回 default。"""
        return self._data.get(key, default)

    def delete(self, key):
        """删除一个键，返回是否真的删掉了。"""
        if key in self._data:
            del self._data[key]
            self._bump(key)
            return True
        return False

    def keys(self):
        """当前所有键的列表。"""
        return list(self._data)

    def snapshot(self):
        """主表当前内容的一份副本。"""
        return dict(self._data)

    def begin(self):
        """开启一个事务。"""
        return Transaction(self)

    def _bump(self, key):
        self._seq += 1
        self._versions[key] = self._seq

    def _version(self, key):
        return self._versions.get(key, 0)


class Transaction:
    """一次事务的读写副本。

    store: 所属的 KVStore。
    事务内 set/delete 的结果先留在事务里，commit 时并回主表。
    """

    def __init__(self, store):
        self._store = store
        self._open = True
        self._base = store.snapshot()
        self._writes = {}
        self._deletes = set()
        self._undo = {}

    def get(self, key, default=None):
        """读取一个键，不存在时返回 default。"""
        self._check_open()
        return self._base.get(key, default)

    def set(self, key, value):
        """在事务内写入或覆盖一个键。"""
        self._check_open()
        if key not in self._undo and key in self._base:
            self._undo[key] = self._base[key]
        self._writes[key] = value
        self._deletes.discard(key)

    def delete(self, key):
        """在事务内删除一个键。"""
        self._check_open()
        self._store._data.pop(key, None)
        self._deletes.add(key)
        self._writes.pop(key, None)

    def commit(self):
        """提交事务，把本事务的结果并回主表。"""
        self._check_open()
        self._store._data = dict(self._writes)
        self._open = False

    def rollback(self):
        """回滚事务，把主表还原成事务开始时的样子。"""
        self._check_open()
        for key, old in self._undo.items():
            self._store._data[key] = old
        self._open = False

    def _check_open(self):
        if not self._open:
            raise RuntimeError("transaction is already closed")
