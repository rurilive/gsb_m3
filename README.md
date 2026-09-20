# shapeq

网关进程内的多租户限流器，纯标准库，无外部依赖。

## 现状

`shapeq/limiter.py` 提供固定窗口计数的 `FixedWindowLimiter`：

- `FixedWindowLimiter(limit, window, clock=time.monotonic)`：limit 为单窗口放行上限，window 为窗口长度（秒），clock 为注入时钟
- `allow(key)` — 放行返回 True 并占掉一个名额，超限返回 False
- `stats()` 返回 `allowed` / `rejected` / `keys` 计数快照
- 窗口按注入时钟对齐到 window 的整数倍，跨窗口自动重新计数；不同 key 配额互不影响
- 内部一把锁保护，多线程单操作安全

## 问题

下游要的是流量整形而不是简单挡回：突发要能被吸收、平常要按速率放。多租户共用一份后端配额时，某个租户突发打满会挤掉其他租户的份额。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_limiter.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 固定窗口 + 令牌桶整形两段演示
python3 -m unittest discover -s tests -v # 基线与新行为测试
```

## 实现说明

- `shapeq/shaper.py` 的 `TokenBucketShaper(rate, capacity, overflow, max_wait, max_queue, clock)` 与旧限流器并存，`allow/stats` 语义不变。
- 每租户一个独立令牌桶：`capacity` 吸收突发，按 `rate` 令牌/秒惰性补充，长期速率不超过 `rate`、瞬时突发不超过 `capacity`。
- 公平靠“不共享”：租户只在自己桶里取令牌，打满只欠自己的债，碰不到别人桶里的令牌，因此没有租户会被邻居饿死。
- 代价是空闲租户的未用配额不会借给忙租户（非 work-conserving）；要共享需另加全局桶层，会重新引入有界干扰。
- 超出按 `overflow` 处理：`REJECT` 立即拒；`QUEUE` 进本租户 FIFO，入队即按补充速率算好 `ready_at` 并预占令牌（桶可为负、不允许插队），超 `max_wait` 或 `max_queue` 分别拒以 `max_wait_exceeded` / `queue_full`。
- 注入时钟推进后调 `pump()` 放行到期请求；默认 `time.monotonic` 时守护线程自动 pump，`wait()` 阻塞取结果。
- `stats()` 新增 `queued`、`tokens_remaining`、`tokens_by_tenant`、`tenants`，并在快照时惰性补充到当前时刻。
- 新行为测试见 `tests/test_shaper.py`，全部用手动时钟对齐补充点与等待上限；基线 `tests/test_limiter.py` 未改动。
