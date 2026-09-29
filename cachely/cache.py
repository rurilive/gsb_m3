"""最朴素的字典缓存，纯标准库。

现有能力（基线）：

- DictCache() 直接用一个 dict 存键值，没有容量上限；
- get(key) 取回值，键存在算命中返回 (True, value) 并把该键的访问计数加一，
  键不存在算未命中返回 (False, None)，未命中不动任何计数；
- set(key, value) 直接写入并返回值，键已存在则覆盖值，访问计数原样保留；
- access_count(key) 查询某个键累计被命中的次数，键从未命中过返回 0；
- len / in 给出条目数与成员判断。

这一层没有任何容量概念，也没有淘汰策略：条目只增不减，写多少留多少，
访问计数只是记着，不参与任何决策。带容量与淘汰策略的缓存要在它之上另建
模块。
"""


class DictCache:
    """无容量上限、无淘汰的字典缓存。"""

    def __init__(self):
        self._data = {}
        self._access = {}

    def get(self, key):
        """取回值。命中返回 (True, value) 并累加访问计数，未命中返回 (False, None)。"""
        if key in self._data:
            self._access[key] = self._access.get(key, 0) + 1
            return (True, self._data[key])
        return (False, None)

    def set(self, key, value):
        """写入并返回值，键已存在则覆盖，访问计数保留。"""
        self._data[key] = value
        return value

    def access_count(self, key):
        """某键累计被命中的次数，从未命中过返回 0。"""
        return self._access.get(key, 0)

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data
