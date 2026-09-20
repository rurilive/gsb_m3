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

- 记账在共享存储：每个 (key, 窗口) 记已批出总额度与各实例租约，申领原子，六台合计不超 limit
- 实例按 `batch` 本地预领，批内放行不走存储；批越大远程往返越少，但闲置额度越多
- 余额三路回收：`release_unused()`/`close()` 主动归还、窗口滚动自动归还、掉线租约到期由他人申领时回收
- 窗口边界以存储时钟为准，申领响应带存储时刻，实例换算到本地时钟，时钟差几秒不会多放
- 存储故障按 key 降级：`on_error` 默认拒绝（fail-closed），`key_policies` 可逐 key 放行（fail-open）
