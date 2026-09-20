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

- 两层分层：`strategies.py` 只算等待秒数（`wait_for(attempt) -> 秒`），`core.py` 的 `RetryExecutor.run` 是唯一重试循环，负责异常判定、预算、回调、睡眠。
- 内置 `FixedBackoff` / `ExponentialBackoff` / `JitteredBackoff` 与循环解耦，三个策略同一条循环，历史分叉已消除。
- 时间统一用单调时钟 `time.monotonic`（原 fixed 误用 `time.time`）；`sleep` 与时钟由 `RetryExecutor` 构造参数注入，默认行为仍是 `time.sleep` / `time.monotonic`，单测可免打补丁。
- 自定义退避曲线：`strategy=` 直接传 `fn(attempt) -> 等待秒数` 的函数，`CallableBackoff` 适配成同一接口，循环零改动即可接入。
- 对外仍是 `retry()` 与 `RetryError`，签名、错误文本、等待序列与回调时序保持不变（见 `tests/test_backoff.py`）。
