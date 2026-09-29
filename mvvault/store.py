"""mvvault 的版本化内存 KV 现有实现，纯标准库，无外部依赖。

把每次写入记成一个带提交时间戳的版本：put 追加一个普通版本，delete 追加一条
删除墓碑版本，get 取当前可见的那一版。每个键维护一条按提交时间戳升序的版本链，
提交时间戳由 store 内部单调计数分配，从 1 起严格递增。

现有对外能力：
  put(key, value)   写入并返回该版本的提交时间戳
  delete(key)       写一条墓碑，返回该键此前是否存在
  get(key)          返回该键当前的值，键不存在或已删返回 None
  keys()            当前存在的键，按升序
  latest_ts         已分配的最大提交时间戳

暂时没有：按时间戳读、快照读、事务与写写冲突检测、历史查询、旧版本回收。
"""

import threading
from collections import namedtuple

Version = namedtuple("Version", ("ts", "value", "deleted"))


class MVStore:
    """一个单机的版本化 KV。

    内部结构：_versions 是键到版本链的映射，链按提交时间戳升序；_last_write
    记每个键最近一次写入的时间戳；_ts 是已分配的最大提交时间戳。所有读写都在
    一把可重入锁下进行，键与值都不做拷贝，取出的值与原对象同一。
    """

    def __init__(self):
        self._versions = {}
        self._last_write = {}
        self._ts = 0
        self._lock = threading.RLock()

    def _bump(self):
        self._ts += 1
        return self._ts

    def _visible(self, key, ts):
        """返回键在时间戳 ts 处可见的那一版，墓碑或不存在返回 None。"""
        found = None
        for version in self._versions.get(key, ()):
            if version.ts <= ts:
                found = version
            else:
                break
        if found is None or found.deleted:
            return None
        return found

    def put(self, key, value):
        """写入一个普通版本，返回它的提交时间戳。"""
        with self._lock:
            ts = self._bump()
            self._versions.setdefault(key, []).append(Version(ts, value, False))
            self._last_write[key] = ts
            return ts

    def delete(self, key):
        """写入一条删除墓碑，返回该键写删除前是否存在。"""
        with self._lock:
            existed = self._visible(key, self._ts) is not None
            ts = self._bump()
            self._versions.setdefault(key, []).append(Version(ts, None, True))
            self._last_write[key] = ts
            return existed

    def get(self, key):
        """返回键当前的值，键不存在或已被删除时返回 None。"""
        with self._lock:
            version = self._visible(key, self._ts)
            return None if version is None else version.value

    def keys(self):
        """当前存在的键，按升序返回。"""
        with self._lock:
            return sorted(k for k in self._versions
                          if self._visible(k, self._ts) is not None)

    @property
    def latest_ts(self):
        """已分配的最大提交时间戳，空 store 为 0。"""
        with self._lock:
            return self._ts
