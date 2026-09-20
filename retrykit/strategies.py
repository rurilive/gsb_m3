"""退避策略层：只负责回答"第 attempt 次失败后等多久"，不碰重试循环。

所有策略实现同一个无状态接口：
    wait_for(attempt) -> float   # attempt 从 1 计

内置 fixed / expo / jitter 三个策略；调用方传入的自定义曲线函数
（签名同样是 wait_for(attempt) -> 等待秒数）由 CallableBackoff 适配，
核心循环无需感知策略是内置的还是外来的。
"""

import random


class Backoff(object):
    """策略基类：输入失败序号，输出下一次重试前的等待秒数。"""

    def wait_for(self, attempt):
        raise NotImplementedError


class FixedBackoff(Backoff):
    """固定间隔：每次失败后都等 delay。"""

    def __init__(self, delay):
        self.delay = delay

    def wait_for(self, attempt):
        return self.delay


class ExponentialBackoff(Backoff):
    """指数退避：第 n 次失败后等 delay * 2**(n-1)，受 max_delay 封顶。"""

    def __init__(self, delay, max_delay=None):
        self.delay = delay
        self.max_delay = max_delay

    def wait_for(self, attempt):
        wait = self.delay * (2 ** (attempt - 1))
        if self.max_delay is not None and wait > self.max_delay:
            wait = self.max_delay
        return wait


class JitteredBackoff(Backoff):
    """全抖动：在 [0, 同 expo 的上限] 内均匀取值。"""

    def __init__(self, delay, max_delay=None, uniform=None):
        self.delay = delay
        self.max_delay = max_delay
        # 默认 None，调用时才解析 random.uniform，保证 monkeypatch 生效。
        self._uniform = uniform

    def wait_for(self, attempt):
        cap = self.delay * (2 ** (attempt - 1))
        if self.max_delay is not None and cap > self.max_delay:
            cap = self.max_delay
        uniform = self._uniform if self._uniform is not None else random.uniform
        return uniform(0.0, cap)


class CallableBackoff(Backoff):
    """适配调用方自定义退避曲线：fn(attempt) -> 等待秒数。"""

    def __init__(self, fn):
        self._fn = fn

    def wait_for(self, attempt):
        return self._fn(attempt)


def build_backoff(strategy, delay, max_delay):
    """按 retry() 的 strategy 参数构造策略对象，未知值抛 ValueError。"""
    if callable(strategy):
        return CallableBackoff(strategy)
    if strategy == "fixed":
        return FixedBackoff(delay)
    if strategy == "expo":
        return ExponentialBackoff(delay, max_delay)
    if strategy == "jitter":
        return JitteredBackoff(delay, max_delay)
    raise ValueError("unknown strategy: %s" % strategy)
