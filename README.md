# breakerbox

可失败调用的重试包装，纯标准库，无外部依赖。

## 现状

breakerbox/guard.py 提供 RetryGuard：

- RetryGuard(retries=0, clock=time.monotonic)：retries 是除首次外的额外重试次数，clock 由构造参数注入
- run(fn, *args, **kwargs)：执行 fn，失败就再试，某次成功立即返回其结果；重试与首次合计 retries + 1 次尝试
- 全部尝试都失败时抛 RetryExhausted，其 attempts 为总尝试次数，last 为最后一次的原始异常
- run_or_none(...)：同上，但耗尽时返回 None
- RetryExhausted：携带 attempts 与 last 的异常类型

## 问题

只有重试这一层，没有别的。失败就闷头再打，下游持续故障时调用方仍一次次压过去，
既不会快速失败也不自愈；每次调用的成败不留痕迹，失败率高低看不出，无从判断
何时该收敛；临时不可用时也没有兜底路径，调用方只能一并失败。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_retry.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）