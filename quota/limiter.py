"""固定窗口计数限流器，单进程内存实现，纯标准库。

每个 key 在 window 秒的窗口里最多放行 limit 个请求；窗口按 clock 读数
对齐切分，跨窗口计数归零。时钟通过 clock 注入（默认 time.monotonic），
测试可换假时钟手动推进，不做真实 sleep。
"""
import threading
import time

DEFAULT_KEY = "default"


class FixedWindowLimiter:
    """单进程固定窗口限流器。

    计数只保存在本进程内存里。多实例部署时各实例各记各的，合起来会
    突破 limit——共享额度是上层要解决的事。
    """

    def __init__(self, limit, window=1.0, clock=time.monotonic):
        if limit <= 0:
            raise ValueError("limit 必须为正数")
        if window <= 0:
            raise ValueError("window 必须为正数")
        self.limit = int(limit)
        self.window = float(window)
        self._clock = clock
        self._lock = threading.Lock()
        self._windows = {}

    def allow(self, key=DEFAULT_KEY):
        """窗口内还有额度则放行并计数，否则拒绝。"""
        with self._lock:
            start, count = self._current(key)
            if count >= self.limit:
                return False
            self._windows[key] = (start, count + 1)
            return True

    def remaining(self, key=DEFAULT_KEY):
        """当前窗口的剩余额度。"""
        with self._lock:
            _start, count = self._current(key)
            return max(0, self.limit - count)

    def _current(self, key):
        """取 key 在当前窗口的计数，跨窗口视作 0（调用方持锁）。"""
        now = self._clock()
        start = now - (now % self.window)
        old_start, count = self._windows.get(key, (None, 0))
        if old_start != start:
            return start, 0
        return start, count
