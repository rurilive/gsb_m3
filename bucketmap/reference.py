"""最朴素的参考实现：dict 直接映射。

单线程、语义与 HashMap 一致，随机对拍时拿它当 oracle：
并发跑完一轮，两边逐键比对，不重不漏。
"""


class PlainMap:
    """基于 dict 的键值表，接口对齐 HashMap 的常用部分。"""

    def __init__(self):
        self._data = {}

    def put(self, key, value):
        """写入并返回原值，键不存在时返回 None。"""
        if value is None:
            raise ValueError("value must not be None")
        prev = self._data.get(key)
        self._data[key] = value
        return prev

    def get(self, key, default=None):
        return self._data.get(key, default)

    def delete(self, key):
        """删除键，返回是否真的删掉了。"""
        if key in self._data:
            del self._data[key]
            return True
        return False

    def items(self):
        return list(self._data.items())

    def keys(self):
        return list(self._data.keys())

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data
