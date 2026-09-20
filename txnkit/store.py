"""进程内键值存储与事务。

单线程模型：KVStore 持有一张键值表，transaction 通过 begin() 开启。
事务开始时给主表拍一份快照，事务内的读走快照，写入先记在写集合里，
提交时逐键并回主表，回滚时丢弃暂存区。每个键带一个版本号，
提交时拿事务开始时记下的版本与主表当前版本比对：本事务写过或删过的键
若在事务开始后被别的事务改过，就抛 ConflictError，整体作废。

所有进出存储边界的值（初始化、set/get、快照）都做深拷贝，
调用方与存储之间不共享嵌套可变结构。
"""

from copy import deepcopy


class ConflictError(RuntimeError):
    """提交时检测到键在事务开始后被其他事务改过。"""

    def __init__(self, keys):
        self.keys = list(keys)
        super().__init__("conflict on keys: " + ", ".join(repr(k) for k in self.keys))


class KVStore:
    """内存键值表。"""

    def __init__(self, initial=None):
        self._data = deepcopy(dict(initial or {}))
        self._versions = {key: 1 for key in self._data}
        self._seq = 1

    def set(self, key, value):
        """写入或覆盖一个键。"""
        self._data[key] = deepcopy(value)
        self._bump(key)

    def get(self, key, default=None):
        """读取一个键，不存在时返回 default。"""
        if key in self._data:
            return deepcopy(self._data[key])
        return deepcopy(default)

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
        return deepcopy(self._data)

    def begin(self):
        """开启一个事务。"""
        return Transaction(self, deepcopy(self._data), dict(self._versions))

    def _bump(self, key):
        self._seq += 1
        self._versions[key] = self._seq


class Transaction:
    """一次事务的读写副本。

    store: 所属的 KVStore。
    base: 事务开始时主表的深拷贝快照，事务内读走它。
    base_versions: 事务开始时各键的版本号，提交时用于冲突检测。
    事务内 set/delete 的结果先留在暂存区里，commit 时逐键并回主表，
    rollback 时整体丢弃，事务期间主表完全不动。
    """

    def __init__(self, store, base, base_versions):
        self._store = store
        self._open = True
        self._base = base
        self._base_versions = base_versions
        self._writes = {}
        self._deletes = {}

    def get(self, key, default=None):
        """读取一个键，不存在时返回 default。"""
        self._check_open()
        if key in self._deletes:
            return deepcopy(default)
        if key in self._writes:
            return deepcopy(self._writes[key])
        if key in self._base:
            return deepcopy(self._base[key])
        return deepcopy(default)

    def set(self, key, value):
        """在事务内写入或覆盖一个键。"""
        self._check_open()
        self._writes[key] = deepcopy(value)
        self._deletes.pop(key, None)

    def delete(self, key):
        """在事务内删除一个键，返回事务视角下它之前是否存在。"""
        self._check_open()
        if key in self._writes:
            existed = True
        elif key in self._deletes:
            existed = False
        else:
            existed = key in self._base
        self._writes.pop(key, None)
        if key in self._base:
            self._deletes[key] = None
        else:
            self._deletes.pop(key, None)
        return existed

    def commit(self):
        """提交事务，把本事务改动的键逐键并回主表。

        本事务写过或删过的键，若在事务开始后被别的事务改过
        （版本号不一致），则判冲突：抛 ConflictError，主表保持原样，
        本事务整体作废。
        """
        self._check_open()
        touched = set(self._writes) | set(self._deletes)
        conflicts = sorted(
            key
            for key in touched
            if self._store._versions.get(key, 0) != self._base_versions.get(key, 0)
        )
        if conflicts:
            raise ConflictError(conflicts)
        for key, value in self._writes.items():
            self._store._data[key] = deepcopy(value)
            self._store._bump(key)
        for key in self._deletes:
            self._store._data.pop(key, None)
            self._store._bump(key)
        self._open = False

    def rollback(self):
        """回滚事务，丢弃暂存区；主表从事务开始以来就没被动过。"""
        self._check_open()
        self._writes.clear()
        self._deletes.clear()
        self._open = False

    def _check_open(self):
        if not self._open:
            raise RuntimeError("transaction is already closed")
