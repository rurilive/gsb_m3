"""shardmap 的基线实现：单字典映射。

FlatMap 是最朴素的映射：get 与 set 直接读写一个内建字典，
没有分片、没有锁、没有并发保护、也没有快照。
"""


class FlatMap:
    """单字典映射，读写都直接落在一个内建字典上。"""

    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def delete(self, key):
        if key in self._data:
            del self._data[key]
            return True
        return False

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)

    def keys(self):
        return list(self._data.keys())

    def items(self):
        return list(self._data.items())

    def snapshot(self):
        return dict(self._data)
