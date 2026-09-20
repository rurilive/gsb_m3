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

- 分三层：`Clock` 只管时钟与 sleep（可用 `use_clock()` 整体注入，默认走标准库）；`Backoff` 策略对象只算第 n 次失败等多久；`retry` 是唯一执行循环，统一负责调用、异常判定、预算、回调。
- 内置 `FixedBackoff` / `ExponentialBackoff` / `JitterBackoff`，由策略名映射，历史等待序列不变。
- 接入自定义退避曲线：直接把 `wait(attempt)` 形式的函数传给 `strategy`，或传 `Backoff` 子类实例；`register_strategy(name, cls)` 可登记成命名策略。
- 因为循环与退避算法彻底解耦，新增曲线只需提供“第几次失败→等几秒”，无需碰执行循环，所以接得住任意自定义曲线。
