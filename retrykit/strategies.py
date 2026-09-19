"""退避策略层。

每个策略只回答一件事：第 attempt 次失败（attempt 从 1 计）之后等多久。
等待之外的所有事情（尝试计数、异常筛选、时间预算、回调、睡眠）都在
retrykit.core 的单一循环里，策略之间不再各抄一份。

自定义退避曲线：写一个签名为 next_delay(attempt, delay, max_delay) ->
秒数 的可调用对象，直接传给 retry(strategy=...) 即可；想保持有状态也可
以传入实现了同名方法的对象。
"""

import random


class BackoffStrategy(object):
    """策略基类：给定失败序号与基础参数，返回下一次重试前的等待秒数。"""

    def next_delay(self, attempt, delay, max_delay):
        raise NotImplementedError


class FixedBackoff(BackoffStrategy):
    """固定间隔：每次失败后都等 delay。"""

    def next_delay(self, attempt, delay, max_delay):
        return delay


class ExponentialBackoff(BackoffStrategy):
    """指数退避：第 n 次失败后的等待为 delay * 2**(n-1)，受 max_delay 封顶。"""

    def next_delay(self, attempt, delay, max_delay):
        wait = delay * (2 ** (attempt - 1))
        if max_delay is not None and wait > max_delay:
            wait = max_delay
        return wait


class FullJitterBackoff(BackoffStrategy):
    """全抖动：在 [0, 同指数退避的上限] 内均匀取值。"""

    def next_delay(self, attempt, delay, max_delay):
        cap = delay * (2 ** (attempt - 1))
        if max_delay is not None and cap > max_delay:
            cap = max_delay
        return random.uniform(0, cap)


class _CallableBackoff(BackoffStrategy):
    """把 next_delay(attempt, delay, max_delay) 形式的可调用对象适配成策略。"""

    def __init__(self, fn):
        self._fn = fn

    def next_delay(self, attempt, delay, max_delay):
        return self._fn(attempt, delay, max_delay)


_STRATEGIES = {
    "fixed": FixedBackoff,
    "expo": ExponentialBackoff,
    "jitter": FullJitterBackoff,
}


def resolve_strategy(strategy):
    """把 retry() 收到的 strategy 参数解析成策略实例。

    内置名查表；可调用对象或带 next_delay 方法的对象视为自定义策略。
    未知字符串沿用历史错误文本。
    """
    if isinstance(strategy, str):
        try:
            return _STRATEGIES[strategy]()
        except KeyError:
            raise ValueError("unknown strategy: %s" % strategy)
    if callable(strategy):
        return _CallableBackoff(strategy)
    if hasattr(strategy, "next_delay"):
        return strategy
    raise TypeError("strategy must be a name, a callable or a BackoffStrategy")
