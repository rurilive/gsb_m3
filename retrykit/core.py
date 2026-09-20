"""重试执行核心。

fixed / expo / jitter 三份历史循环已收敛成 RetryExecutor.run 这一个循环：
循环只管"调用 -> 判重试 -> 问策略要等待秒数 -> 查时间预算 -> 回调 -> 睡眠"，
等待曲线全部下沉到 retrykit.strategies。睡眠和时钟通过构造参数注入，
默认仍走 time.sleep / time.monotonic，单测无需打模块级补丁。
"""

import time

from retrykit.strategies import build_backoff


class RetryError(Exception):
    """attempts 用尽或时间预算耗尽时抛出。"""


class RetryExecutor(object):
    """单一重试执行器，三个内置策略与自定义曲线共用同一条循环。"""

    def __init__(self, backoff, attempts, timeout=None, retry_on=(Exception,),
                 on_retry=None, sleep=None, clock=None):
        self.backoff = backoff
        self.attempts = attempts
        self.timeout = timeout
        self.retry_on = retry_on
        self.on_retry = on_retry
        # 运行时才解析，保留对 time.sleep / time.monotonic 打补丁的兼容。
        self._sleep = sleep
        self._clock = clock

    def _sleep_now(self, seconds):
        sleep = self._sleep if self._sleep is not None else time.sleep
        sleep(seconds)

    def _now(self):
        clock = self._clock if self._clock is not None else time.monotonic
        return clock()

    def run(self, fn):
        started = self._now()
        for attempt in range(1, self.attempts + 1):
            try:
                return fn()
            except Exception as exc:
                if not isinstance(exc, self.retry_on):
                    raise
                if attempt >= self.attempts:
                    raise RetryError(
                        "gave up after %d attempts, last error: %r" % (attempt, exc))
                wait = self.backoff.wait_for(attempt)
                if self.timeout is not None and self._now() - started >= self.timeout:
                    raise RetryError(
                        "budget of %.2fs exceeded after %d attempts, last error: %r"
                        % (self.timeout, attempt, exc))
                if self.on_retry is not None:
                    self.on_retry(attempt, exc, wait)
                self._sleep_now(wait)


def retry(fn, attempts=3, strategy="fixed", delay=1.0, max_delay=None,
          timeout=None, retry_on=(Exception,), on_retry=None):
    """执行 fn，最多 attempts 次（含首次），失败按 strategy 等待后重试。

    - strategy: "fixed" 固定间隔 / "expo" 指数退避 / "jitter" 全抖动；
      也可传自定义曲线函数 fn(attempt) -> 等待秒数
    - delay: 基础等待秒数；expo/jitter 第 n 次失败后的上限是 delay * 2**(n-1)
    - max_delay: expo/jitter 单次等待上限，None 表示不设上限
    - timeout: 整个调用的时间预算（秒，monotonic），某次失败后已超预算则
      立刻放弃，与重试耗尽抛的 RetryError 文本不同
    - retry_on: 可重试异常类元组，不在里面的异常原样抛出
    - on_retry(attempt, exc, wait): 即将重试前回调，attempt 从 1 计，
      最后一次失败不回调
    - 成功时原样返回 fn 的返回值（falsy 也算成功），放弃时抛 RetryError
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if delay < 0:
        raise ValueError("delay must be >= 0")
    backoff = build_backoff(strategy, delay, max_delay)
    return RetryExecutor(
        backoff, attempts=attempts, timeout=timeout, retry_on=retry_on,
        on_retry=on_retry).run(fn)
