"""重试执行核心：单一执行循环 + 可插拔退避策略。

历史上 fixed / expo / jitter 各抄了一份循环，2018 年以来的语义差异
（时间预算统一用 time.monotonic 判定）已在此收敛；行为以
tests/test_backoff.py 为准。
"""

import time

from retrykit.strategies import resolve_strategy


class RetryError(Exception):
    """attempts 用尽或时间预算耗尽时抛出。"""


def retry(fn, attempts=3, strategy="fixed", delay=1.0, max_delay=None,
          timeout=None, retry_on=(Exception,), on_retry=None, _sleep=None):
    """执行 fn，最多 attempts 次（含首次），失败按 strategy 等待后重试。

    - strategy: "fixed" 固定间隔 / "expo" 指数退避 / "jitter" 全抖动；
      也可直接传 callable fn(attempt) -> 等待秒数，自定义退避曲线
    - delay: 基础等待秒数；expo/jitter 第 n 次失败后的上限是 delay * 2**(n-1)
    - max_delay: expo/jitter 单次等待上限，None 表示不设上限
    - timeout: 整个调用的时间预算（秒），某次失败后已超预算则立刻放弃，
      与重试耗尽抛的 RetryError 文本不同
    - retry_on: 可重试异常类元组，不在里面的异常原样抛出
    - on_retry(attempt, exc, wait): 即将重试前回调，attempt 从 1 计，
      最后一次失败不回调
    - _sleep: 测试注入用的 sleep 实现，默认 time.sleep（非公开参数）
    - 成功时原样返回 fn 的返回值（falsy 也算成功），放弃时抛 RetryError
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if delay < 0:
        raise ValueError("delay must be >= 0")
    backoff = resolve_strategy(strategy, delay, max_delay)
    sleep = _sleep if _sleep is not None else time.sleep

    started = time.monotonic()
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on as e:
            if attempt >= attempts:
                raise RetryError(
                    "gave up after %d attempts, last error: %r" % (attempt, e))
            if timeout is not None and time.monotonic() - started >= timeout:
                raise RetryError(
                    "budget of %.2fs exceeded after %d attempts, last error: %r"
                    % (timeout, attempt, e))
            wait = backoff.wait(attempt)
            if on_retry is not None:
                on_retry(attempt, e, wait)
            sleep(wait)
