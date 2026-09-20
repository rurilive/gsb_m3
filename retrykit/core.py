"""重试执行核心。2018 年给任务队列写的兜底层。

分层：
  策略对象（``Backoff`` 子类）只负责算出第 n 次失败后等多久；
  执行循环（``retry``）只有一份，负责调用、异常判定、时间预算、回调和睡眠；
  时钟（``Clock``）把 monotonic/sleep 收敛到一处，可整体注入。

fixed / expo / jitter 的历史语义完全保留，以 tests/test_backoff.py 为准。
"""

import random
import time
from contextlib import contextmanager


class RetryError(Exception):
    """attempts 用尽或时间预算耗尽时抛出。"""


class Clock(object):
    """时钟与睡眠的单一入口，默认走标准库，可在测试中整体替换。"""

    def monotonic(self):
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)


_clock = Clock()


@contextmanager
def use_clock(clock):
    """临时替换 retry 使用的时钟（需提供 monotonic()/sleep(seconds)）。"""
    global _clock
    previous = _clock
    _clock = clock
    try:
        yield
    finally:
        _clock = previous


class Backoff(object):
    """退避策略基类：给定 delay/max_delay，算出第 attempt 次失败后的等待。"""

    def __init__(self, delay, max_delay=None):
        self.delay = delay
        self.max_delay = max_delay

    def wait(self, attempt):
        raise NotImplementedError


class FixedBackoff(Backoff):
    """固定间隔，历史上不受 max_delay 影响。"""

    def wait(self, attempt):
        return self.delay


class ExponentialBackoff(Backoff):
    """指数退避：delay * 2**(attempt-1)，可被 max_delay 封顶。"""

    def wait(self, attempt):
        wait = self.delay * (2 ** (attempt - 1))
        if self.max_delay is not None and wait > self.max_delay:
            return self.max_delay
        return wait


class JitterBackoff(ExponentialBackoff):
    """全抖动：在 [0, 同 expo 的上限] 内均匀取值。"""

    def wait(self, attempt):
        cap = super(JitterBackoff, self).wait(attempt)
        return random.uniform(0, cap)


_STRATEGIES = {
    "fixed": FixedBackoff,
    "expo": ExponentialBackoff,
    "jitter": JitterBackoff,
}


def register_strategy(name, backoff_cls):
    """登记命名策略，之后 retry(strategy=name) 即可使用。"""
    _STRATEGIES[name] = backoff_cls


class _CallableBackoff(Backoff):
    """把调用方传入的退避曲线函数适配成策略对象。"""

    def __init__(self, curve):
        super(_CallableBackoff, self).__init__(delay=0.0)
        self._curve = curve

    def wait(self, attempt):
        return self._curve(attempt)


def _resolve_strategy(strategy, delay, max_delay):
    if isinstance(strategy, str):
        backoff_cls = _STRATEGIES.get(strategy)
        if backoff_cls is None:
            raise ValueError("unknown strategy: %s" % strategy)
        return backoff_cls(delay, max_delay)
    if isinstance(strategy, Backoff):
        return strategy
    if callable(strategy):
        return _CallableBackoff(strategy)
    raise ValueError("unknown strategy: %r" % (strategy,))


def retry(fn, attempts=3, strategy="fixed", delay=1.0, max_delay=None,
          timeout=None, retry_on=(Exception,), on_retry=None):
    """执行 fn，最多 attempts 次（含首次），失败按 strategy 等待后重试。

    - strategy: "fixed" 固定间隔 / "expo" 指数退避 / "jitter" 全抖动；
      也可直接传 Backoff 实例或 wait(attempt) 形式的退避曲线函数
    - delay: 基础等待秒数；expo/jitter 第 n 次失败后的上限是 delay * 2**(n-1)
    - max_delay: expo/jitter 单次等待上限，None 表示不设上限
    - timeout: 整个调用的时间预算（秒），某次失败后已超预算则立刻放弃，
      与重试耗尽抛的 RetryError 文本不同
    - retry_on: 可重试异常类元组，不在里面的异常原样抛出
    - on_retry(attempt, exc, wait): 即将重试前回调，attempt 从 1 计，
      最后一次失败不回调
    - 成功时原样返回 fn 的返回值（falsy 也算成功），放弃时抛 RetryError
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if delay < 0:
        raise ValueError("delay must be >= 0")

    backoff = _resolve_strategy(strategy, delay, max_delay)

    started = _clock.monotonic()
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on as e:
            if attempt >= attempts:
                raise RetryError(
                    "gave up after %d attempts, last error: %r" % (attempt, e))
            if timeout is not None and _clock.monotonic() - started >= timeout:
                raise RetryError(
                    "budget of %.2fs exceeded after %d attempts, last error: %r"
                    % (timeout, attempt, e))
            wait = backoff.wait(attempt)
            if on_retry is not None:
                on_retry(attempt, e, wait)
            _clock.sleep(wait)
