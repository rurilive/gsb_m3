"""一张内存字典 KV（改造前的朴素基线）。

现有能力：按字符串主键存一份值，写入或覆盖一条，按键取回值，按键删除并回报
是否删到，按写入顺序列出全部主键，问条数与命中未命中计数。
所有 key 都没有租约，谁能写取决于调用方自己守规矩，写进去就一直留着。
按键租约、续约、看门狗回收、抢占与 fencing token、观察者通知与并发下的租约
唯一性尚未提供。
"""

_UNSET = object()


class LeaseKV:
    """无租约的字典 KV。

    data 以字符串主键为键，值是该主键对应的一份值。
    写入同名主键即覆盖，主键在首次写入时的位置保持不变。
    取回的值按值拷贝，改动它不会影响 KV 里存的内容。
    """

    def __init__(self):
        self._data = {}
        self._hits = 0
        self._misses = 0

    def _check_key(self, key):
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        return key

    def put(self, key, value):
        """写入或覆盖一条，同名主键覆盖，位置不变，值按值拷贝存下。"""
        self._check_key(key)
        if value is None:
            raise ValueError("value must not be None")
        self._data[key] = _copy_value(value)

    def get(self, key, default=None):
        """按键取回值的一份拷贝，键不存在返回 default，并记一次命中或未命中。"""
        self._check_key(key)
        if key not in self._data:
            self._misses += 1
            return default
        self._hits += 1
        return _copy_value(self._data[key])

    def delete(self, key):
        """按键删除，删到返回 True，键本来就不在返回 False。"""
        self._check_key(key)
        if key in self._data:
            del self._data[key]
            return True
        return False

    def keys(self):
        """按写入顺序给出全部主键的元组。"""
        return tuple(self._data)

    def contains(self, key):
        """键是否在 KV 里。"""
        self._check_key(key)
        return key in self._data

    def stats(self):
        """计数快照，返回独立的字典。"""
        return {
            "live": len(self._data),
            "hits": self._hits,
            "misses": self._misses,
        }

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return "LeaseKV(live=%d)" % len(self._data)


def _copy_value(value):
    """按值拷贝，容器类值取一份浅拷贝，其余不可变值原样返回。"""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    if isinstance(value, set):
        return set(value)
    return value