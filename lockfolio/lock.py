"""朴素全局互斥锁。

一张表记录每个 key 当前的持有者，取锁成功就把持有者写进去，释放时清掉。
没有租约、没有过期、没有续约，也没有并发获取时的排队。
时钟由构造参数 clock 注入，缺省用 time.monotonic，便于测试推进时间。
"""

import time


class MutexLock:
    """按 key 互斥的锁：同一 key 同一时刻只允许一个持有者。"""

    def __init__(self, clock=None):
        self._clock = clock or time.monotonic
        self._owners = {}

    def acquire(self, key, owner):
        """尝试获取 key 的锁。

        成功时记录 owner 并返回 True；已被别人持有时返回 False，不改动现状。
        同一个 owner 重复获取视为失败，返回 False。
        """
        if key in self._owners:
            return False
        self._owners[key] = owner
        return True

    def release(self, key, owner):
        """释放 key 的锁。

        只有当前持有者本人能释放：owner 对得上返回 True 并清掉记录，
        key 没被持有或 holder 不是 owner 时返回 False。
        """
        if self._owners.get(key) != owner:
            return False
        del self._owners[key]
        return True

    def holder(self, key):
        """返回 key 当前持有者，没人持有则为 None。"""
        return self._owners.get(key)

    def is_locked(self, key):
        """key 是否正被持有。"""
        return key in self._owners

    def keys(self):
        """当前被持有的全部 key 快照。"""
        return list(self._owners.keys())