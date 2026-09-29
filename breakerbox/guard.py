"""可失败调用的朴素重试包装（改造前的基线实现）。

只有一件事：把给定的函数跑一遍，失败就再跑，最多重试 retries 次，
某次成功立即返回其结果。没有任何状态，没有统计，也没有等待。
"""

import time


class RetryExhausted(Exception):
    """重试耗尽：携带总尝试次数与最后一次的原始异常。"""

    def __init__(self, attempts, last):
        super().__init__(f"retry exhausted after {attempts} attempt(s)")
        self.attempts = attempts
        self.last = last


class RetryGuard:
    """朴素重试包装：失败重试固定次数，成功即返回。

    retries: 除首次以外的额外重试次数，缺省 0 表示只试一次。
    clock:   返回当前时刻的可调用对象，默认 time.monotonic。
    """

    def __init__(self, retries=0, clock=time.monotonic):
        if retries < 0:
            raise ValueError("retries must be >= 0")
        self._retries = retries
        self._clock = clock

    @property
    def retries(self):
        """额外重试次数。"""
        return self._retries

    def run(self, fn, *args, **kwargs):
        """执行 fn，失败则重试；某次成功立即返回结果，全部失败抛 RetryExhausted。"""
        last = None
        for attempt in range(self._retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # 朴素实现：任何异常都重试
                last = exc
        raise RetryExhausted(self._retries + 1, last)

    def run_or_none(self, fn, *args, **kwargs):
        """同 run，但重试耗尽时返回 None 而不是抛错。"""
        try:
            return self.run(fn, *args, **kwargs)
        except RetryExhausted:
            return None
