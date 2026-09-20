# quota

网关的多实例限流模块，纯标准库，无外部依赖。

## 现状

`quota/limiter.py` 提供 `FixedWindowLimiter`：按 key 做固定窗口计数，
窗口内放行到 `limit` 为止，跨窗口计数归零。窗口按注入时钟对齐切分，
`clock` 默认 `time.monotonic`，可构造传入假时钟。

接口：

- `allow(key="default")` — 有额度则放行并计数，否则拒绝
- `remaining(key="default")` — 当前窗口剩余额度

## 问题

计数只存在本进程内存里。服务从两台扩到六台后，每个实例各限各的，
同一个 key 的实际放行量随实例数一起放大，上游按总量给的配额被整体击穿。

## 目标

见任务描述。约束：

- `tests/test_limiter.py` 是行为基线，一个字不改
- 时钟与共享存储都要可注入，测试不做真实 sleep
- 纯标准库

## 运行

```bash
python3 demo.py                          # 限流现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 额度记账：共享存储按 (key, 窗口起点) 记租约，`acquire` 原子预领、`release` 归还；`InMemoryLeaseStore` 供测试，生产换 Redis+Lua 实现同一接口。
- 预领粒度：`batch` 参数（默认 `limit//10`），本地花完再领，远程往返从每请求一次降为每批一次。
- 回收：租约带 `lease_ttl`（默认 `max(5s, 2*window)`），实例掉线由存储侧到期回收；`close()` 或跨窗口时主动归还没用完的。
- 窗口对齐：窗口起点以存储时钟为准，本地时钟只按最近一次测得的偏移推算边界，实例间差几秒不影响对齐。
- 降级口径：存储故障时按 key 走 `failure_policy`/`key_policies`，`open` 放行、`closed` 拒绝，默认 `closed`。
