"""精确去重计数。

DistinctCounter 把见过的 key 原样存进 set，add 告诉调用方这次是不是新的，
count 给当前不同 key 的个数。结果精确，代价是内存随不同 key 数线性增长。
"""

import threading


class DistinctCounter:
    """基于 set 的去重计数器。"""

    def __init__(self):
        self._seen = set()
        self._lock = threading.Lock()

    def add(self, key):
        """记一个 key，首次出现返回 True，重复出现返回 False。"""
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            return True

    def count(self):
        """当前不同 key 的个数。"""
        with self._lock:
            return len(self._seen)

    def __contains__(self, key):
        """key 是否出现过。"""
        with self._lock:
            return key in self._seen

    def reset(self):
        """清空，回到空计数器状态。"""
        with self._lock:
            self._seen.clear()
