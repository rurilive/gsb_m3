"""超时与耗时：给一段等待定上限，给一段过程量长度。

巡检脚本里到处在用：Deadline 定一个超时秒数，循环里反复问还剩多久、
到没到；Stopwatch 量一段动作花了多久。两个都从注入的 TimeSource 读数，
起点在构造时记下。
"""


class Deadline:
    """一个超时上限，反复问剩余与是否到期。"""

    def __init__(self, source, timeout):
        if timeout < 0:
            raise ValueError("超时上限不能为负")
        self._source = source
        self._timeout = float(timeout)
        self._start = self._source.wall()

    @property
    def timeout(self):
        return self._timeout

    def elapsed(self):
        """从起算到现在过了多久。"""
        return self._source.wall() - self._start

    def remaining(self):
        """还剩多少秒，可能为负。"""
        return self._timeout - self.elapsed()

    def expired(self):
        """到没到期。"""
        return self.remaining() <= 0.0

    def extend(self, seconds):
        """把超时上限往后挪一段，重试之前用。"""
        self._timeout += float(seconds)

    def reset(self):
        """重新起算。"""
        self._start = self._source.wall()


class Stopwatch:
    """量一段耗时，可重启。"""

    def __init__(self, source):
        self._source = source
        self._start = self._source.wall()

    def elapsed(self):
        """从起算到现在过了多久。"""
        return self._source.wall() - self._start

    def restart(self):
        """从现在重新起算。"""
        self._start = self._source.wall()
