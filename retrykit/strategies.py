"""退避策略对象：给定刚失败的尝试次数（从 1 计），返回重试前的等待秒数。

核心循环只依赖 wait(attempt) 这一个接口；新增退避曲线在这里加一个类，
或让调用方直接传 callable，由 resolve_strategy 包成策略对象。
"""

import random


class FixedStrategy(object):
    """固定间隔。"""

    def __init__(self, delay, max_delay=None):
        self.delay = delay

    def wait(self, attempt):
        return self.delay


class ExpoStrategy(object):
    """指数退避：第 n 次失败后等待 delay * 2**(n-1)，可被 max_delay 截断。"""

    def __init__(self, delay, max_delay=None):
        self.delay = delay
        self.max_delay = max_delay

    def wait(self, attempt):
        wait = self.delay * (2 ** (attempt - 1))
        if self.max_delay is not None and wait > self.max_delay:
            wait = self.max_delay
        return wait


class JitterStrategy(ExpoStrategy):
    """全抖动：在 [0, 同 expo 的上限] 内均匀取值。"""

    def wait(self, attempt):
        cap = super(JitterStrategy, self).wait(attempt)
        return random.uniform(0, cap)


class CallableStrategy(object):
    """调用方自定义退避曲线：fn(attempt) -> 等待秒数。"""

    def __init__(self, fn):
        self.fn = fn

    def wait(self, attempt):
        return self.fn(attempt)


_NAMED = {
    "fixed": FixedStrategy,
    "expo": ExpoStrategy,
    "jitter": JitterStrategy,
}


def resolve_strategy(strategy, delay, max_delay):
    """把 strategy 参数统一解析成策略对象。"""
    if isinstance(strategy, str):
        try:
            cls = _NAMED[strategy]
        except KeyError:
            raise ValueError("unknown strategy: %s" % strategy)
        return cls(delay, max_delay)
    if callable(strategy):
        return CallableStrategy(strategy)
    raise ValueError("unknown strategy: %s" % strategy)
