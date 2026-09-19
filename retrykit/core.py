"""重试执行核心：所有策略共用同一条重试循环。

历史上 fixed / expo / jitter 各抄了一份循环（连时间源都不统一）。现在
循环只有一份，策略差异全部收敛到 retrykit.strategies；时钟与睡眠通过
RetryLoop 的构造参数注入，默认接 time.monotonic / time.sleep，行为与
2018 年起被 tests/test_backoff.py 锁定的完全一致。
"""

import time

from retrykit.strategies import resolve_strategy


class RetryError(Exception):
    """attempts 用尽或时间预算耗尽时抛出。"""


class RetryLoop(object):
    """单一重试执行器。

    sleep 与 clock 可注入：测试或调用方传入自己的实现即可驱动时间，不必
    再打 time 模块的补丁；缺省使用 time.sleep 与 time.monotonic。
    """

    def __init__(self, sleep=None, clock=None):
        # None 时在构造这一刻才取 time 模块上的实现，保证调用方对
        # time.sleep / time.monotonic 的补丁（以及本类的注入）都生效。
        self._sleep = time.sleep if sleep is None else sleep
        self._clock = time.monotonic if clock is None else clock

    def run(self, fn, attempts, strategy, delay, max_delay,
            timeout, retry_on, on_retry):
        if attempts < 1:
            raise ValueError("attempts must be >= 1")
        if delay < 0:
            raise ValueError("delay must be >= 0")
        backoff = resolve_strategy(strategy)

        started = self._clock()
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except Exception as exc:
                if not isinstance(exc, retry_on):
                    raise
                if attempt >= attempts:
                    raise RetryError(
                        "gave up after %d attempts, last error: %r"
                        % (attempt, exc))
                wait = backoff.next_delay(attempt, delay, max_delay)
                if timeout is not None and self._clock() - started >= timeout:
                    raise RetryError(
                        "budget of %.2fs exceeded after %d attempts, last error: %r"
                        % (timeout, attempt, exc))
                if on_retry is not None:
                    on_retry(attempt, exc, wait)
                self._sleep(wait)


def retry(fn, attempts=3, strategy="fixed", delay=1.0, max_delay=None,
          timeout=None, retry_on=(Exception,), on_retry=None):
    """执行 fn，最多 attempts 次（含首次），失败按 strategy 等待后重试。

    - strategy: "fixed" 固定间隔 / "expo" 指数退避 / "jitter" 全抖动；
      也接受 next_delay(attempt, delay, max_delay) 形式的可调用对象或
      BackoffStrategy 实例作为自定义退避曲线
    - delay: 基础等待秒数；expo/jitter 第 n 次失败后的上限是 delay * 2**(n-1)
    - max_delay: expo/jitter 单次等待上限，None 表示不设上限
    - timeout: 整个调用的时间预算（秒），某次失败后已超预算则立刻放弃，
      与重试耗尽抛的 RetryError 文本不同
    - retry_on: 可重试异常类元组，不在里面的异常原样抛出
    - on_retry(attempt, exc, wait): 即将重试前回调，attempt 从 1 计，
      最后一次失败不回调
    - 成功时原样返回 fn 的返回值（falsy 也算成功），放弃时抛 RetryError
    """
    return RetryLoop().run(
        fn, attempts, strategy, delay, max_delay,
        timeout, retry_on, on_retry)
