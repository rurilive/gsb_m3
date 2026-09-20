"""基于文件锁的主备选举：抢到锁文件就是主，撒手就让位。

同一台机器上多个进程、或多台机器挂在同一块共享存储上时，用非阻塞排他锁
保证任意时刻只有一个持有者。clock 可注入，方便测试里推进或拨动时间。
"""
import fcntl
import os
import time


class FileLockElection:
    """用 flock 抢占锁文件的简单选主器。

    try_acquire() 试着把锁文件锁上，成功即成为主；release() 解锁让位。
    锁由内核随进程退出自动释放，所以进程崩掉不会把主位永久占住。
    """

    def __init__(self, path, node_id, clock=time.time):
        self._path = path
        self._node_id = node_id
        self._clock = clock
        self._fd = None
        self._held_since = None

    @property
    def node_id(self):
        return self._node_id

    def is_primary(self):
        return self._fd is not None

    def try_acquire(self):
        """尝试成为主。已经在主位返回 True；被别人占着返回 False。"""
        if self._fd is not None:
            return True
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        os.ftruncate(fd, 0)
        os.write(fd, self._node_id.encode("utf-8"))
        self._fd = fd
        self._held_since = self._clock()
        return True

    def release(self):
        """主动让位，把主位交出去；本来就不是主则什么都不做。"""
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        self._held_since = None
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    @property
    def held_since(self):
        """成为主的时刻；不是主时返回 None。"""
        return self._held_since

    def current_holder(self):
        """读出锁文件里记的持有者名字；没人持有时返回 None。"""
        try:
            with open(self._path, "rb") as f:
                return f.read().decode("utf-8") or None
        except FileNotFoundError:
            return None

    def close(self):
        self.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
