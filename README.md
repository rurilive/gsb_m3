# retrykit

任务队列的重试兜底层，2018 年上线。纯标准库，无外部依赖。

## 对外 API

- `retry(fn, attempts=3, strategy="fixed", delay=1.0, max_delay=None, timeout=None, retry_on=(Exception,), on_retry=None)`
  - `attempts`：总尝试次数（含首次），小于 1 抛 ValueError
  - `strategy`：`"fixed"` 固定间隔 / `"expo"` 指数退避（第 n 次失败后等待 `delay * 2**(n-1)`）/ `"jitter"` 在 `[0, 同 expo 的上限]` 内均匀取值；其他值抛 ValueError
  - `max_delay`：expo/jitter 单次等待上限，None 不设上限
  - `timeout`：整个调用的时间预算（秒），某次失败后已超预算则立刻放弃，错误文本与重试耗尽不同
  - `retry_on`：可重试异常类元组，不在里面的异常原样抛出
  - `on_retry(attempt, exc, wait)`：即将重试前回调，attempt 从 1 计；最后一次失败不回调
- 放弃时抛 `RetryError`，成功时原样返回 fn 的返回值（falsy 也算成功）

行为细节（等待序列、预算边界、回调时序、错误文本）以 `tests/test_backoff.py` 为准。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- `retrykit/strategies.py`：策略层，只算等待秒数；`FixedBackoff`/`ExponentialBackoff`/`FullJitterBackoff` 实现统一接口 `next_delay(attempt, delay, max_delay)`。
- `retrykit/core.py`：唯一的重试循环 `RetryLoop`，集中处理尝试计数、异常筛选、时间预算、`on_retry` 回调和错误文本，不再每策略一份。
- 时间与睡眠是 `RetryLoop(sleep=..., clock=...)` 的注入依赖，默认 `time.sleep`/`time.monotonic`，单测可直接传假时钟，无需打补丁。
- `retry()` 签名与行为不变，内部只构造默认 `RetryLoop` 执行；`__init__.py` 仍只导出 `retry`、`RetryError`。
- 接入自定义曲线：写一个 `next_delay(attempt, delay, max_delay) -> 秒数` 的函数或策略对象，传给 `retry(strategy=...)`；循环、预算、回调全部复用，曲线可有状态。
