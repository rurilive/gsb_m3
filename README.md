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

- `retrykit/core.py`：唯一的重试执行循环，负责尝试计数、时间预算（统一 `time.monotonic`）、`retry_on` 过滤、`on_retry` 回调和 `RetryError` 文本，不关心等待时长怎么算。
- `retrykit/strategies.py`：策略对象层，接口只有一个 `wait(attempt)`（attempt 为刚失败的次数，从 1 计），返回本次重试前等待秒数；fixed/expo/jitter 各是一个类，由 `resolve_strategy` 按名字解析。
- sleep 通过非公开参数 `retry(..., _sleep=...)` 注入，默认 `time.sleep`，单测无需再打补丁。
- 自定义退避曲线：把 `strategy` 直接传成可调用对象 `fn(attempt) -> 秒数`，`resolve_strategy` 会包成策略对象走同一个循环，核心零改动。
