# ratelimit

按 key 的请求限流，纯标准库，无外部依赖。

## 现状

`ratelimit/limiter.py` 提供固定窗口限流器 `FixedWindowLimiter`：

- `FixedWindowLimiter(limit, window, clock=None)`：每 window 秒内每 key 最多放过 limit 次
- `allow(key, n=1)`：尝试放行 n 次，返回实际放行次数（额度不足时只放行剩余部分）
- `remaining(key)`：当前窗口内该 key 的剩余额度
- clock 可注入，默认 `time.monotonic`

## 问题

固定窗口在窗口边界有突发放行；不同业务线希望在同一入口按策略限流，
且需要按 key 的动态配额。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_limiter.py` 基线保持一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
