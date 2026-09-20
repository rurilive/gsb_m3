# shapeq

网关进程内的多租户限流器，纯标准库，无外部依赖。

## 现状

`shapeq/limiter.py` 提供固定窗口计数的 `FixedWindowLimiter`：

- `FixedWindowLimiter(limit, window, clock=time.monotonic)`：limit 为单窗口放行上限，window 为窗口长度（秒），clock 为注入时钟
- `allow(key)` — 放行返回 True 并占掉一个名额，超限返回 False
- `stats()` 返回 `allowed` / `rejected` / `keys` 计数快照
- 窗口按注入时钟对齐到 window 的整数倍，跨窗口自动重新计数；不同 key 配额互不影响
- 内部一把锁保护，多线程单操作安全

`shapeq/shaper.py` 另提供令牌桶整形器 `TokenBucketShaper`，老类语义不变：

- `TokenBucketShaper(capacity, refill_rate, global_capacity=None, global_refill_rate=None, policy=REJECT, max_wait=1.0, clock=time.monotonic, sleep=time.sleep)`
- 每租户一个令牌桶（容量 `capacity`、补充速率 `refill_rate` 个/秒），突发由存量令牌吸收，平时按速率放行
- 可选共享全局桶代表后端总配额：一次放行须同时持有租户令牌与全局令牌，单个租户打满只影响自己
- `try_acquire(tenant)` 返回 `ShaperDecision`（`allowed` / `queued` / `rejected`）；`wait()` 等排队结果；`acquire()` 一步到位
- `policy=REJECT` 没令牌立即拒（`reason="rate_limited"`）；`policy=QUEUE` 按补充节奏排队，超过 `max_wait` 以 `reason="wait_timeout"` 拒绝
- `stats()` 返回 `allowed` / `rejected` / `queued`、每租户剩余令牌 `tokens` 与 `global_tokens`

## 背景

下游要的是流量整形而不是简单挡回：突发要能被吸收、平常要按速率放。多租户共用一份后端配额时，某个租户突发打满会挤掉其他租户的份额。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_limiter.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 固定窗口计数演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 令牌惰性补充：只在申请/查 stats 时按时钟把余额补到 min(容量, 余额+速率×经过时间)，无后台线程。
- 两级令牌桶：租户桶限各租户速率与突发，全局桶代表共享后端配额；两者都拿到令牌才放行。
- 公平取舍：配额按租户静态切分，单租户最多按自己的速率消耗全局额度，打满也吃不掉别人那份。
- 代价是不"工作守恒"：没人用的空闲份额不会自动借给别人，换来的是各租户份额可预测、互不干扰。
- 配置建议：各租户速率之和不超过全局补充速率；全局容量建议 ≥（租户数−1）×租户容量+1。
- QUEUE 只预占本租户速率下的未来令牌，队列有 FIFO 顺序与 `max_wait` 上限；所有时间点均由注入时钟确定。
