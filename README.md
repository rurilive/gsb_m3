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
