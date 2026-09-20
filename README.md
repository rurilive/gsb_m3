# timeoutkit

调用编排层沉淀下来的小库：每次调用带预算，支持超时与取消传播，纯标准库，
无外部依赖。时钟可注入，便于测试。

## 模块说明

`timeoutkit/clock.py` 提供时钟抽象 `Clock`：

- `SystemClock`：进程默认时钟，`monotonic()` / `time()` / `sleep()`
- `FakeClock`：手动推进，`advance()` 推进真实时间，`jump_wall()` 只拨墙钟
  （模拟 NTP 校时），供测试注入

`timeoutkit/deadline.py` 提供 `Deadline(budget, clock)`：把相对预算换算成
绝对到期时刻，`remaining()` 给出剩余秒数，`expired()` 判断是否耗尽。

`timeoutkit/core.py` 提供 `CallContext` 与 `call`：

- `CallContext(clock=None, timeout=None, parent=None)`：调用上下文，携带预算、
  父子关系与取消状态
- `ctx.child(timeout=None)`：派生一个子上下文，用于限制下游步骤
- `ctx.remaining()` / `ctx.expired()`：查看剩余预算 / 是否耗尽
- `ctx.cancel()`：取消本上下文以及所有派生出来的子上下文
- `ctx.check()`：协作式取消点，被取消时抛 `Cancelled`
- `call(fn, timeout=None, ctx=None)`：在预算内执行 `fn`，超出预算抛 `Timeout`；
  未给 `ctx` 时按 `timeout` 新建根上下文

`timeoutkit/__init__.py` 导出 `CallContext`、`call`、`Deadline`、`Cancelled`、
`Timeout` 以及三个时钟类。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## Known Issues

以下四类线上现象已在本次修复中根除，根因记录如下：

- **校时后请求卡死或被提前掐断**：`Deadline` 原来用墙钟（`Clock.time()`）
  记录到期时刻。墙钟被 NTP 回拨时，到期时刻跟着后移，本该超时的请求
  一直卡住；墙钟前拨时，剩余预算被凭空吞掉，请求提前被判超时。现改为
  单调钟（`Clock.monotonic()`）度量预算，校时不再影响超时判定。
- **父层已超时、子调用仍跑满自己的预算**：`remaining()` / `expired()`
  原来只看自身预算，子上下文配 5 秒、父级只剩 800 毫秒时，子级会按
  自己的节奏跑满。现沿父链取最紧的预算：子级可用时间不超过任何一级
  祖先的剩余时间。
- **上游已取消，调用方仍阻塞到预算耗尽、后台写继续裸奔**：`call()` 原来
  只在 `job.done` 上等待，取消事件无法唤醒等待方。现等待循环同时监听
  取消，取消后约 10 毫秒内抛出 `Cancelled`。注意 Python 无法强杀线程，
  正在执行的被调方仍需周期性调用 `ctx.check()` 才能尽快停下。
- **已取消的上下文照样发起新调用**：`call()` 原来不校验取消状态，拿到
  作废上下文仍会执行 `fn`，导致已取消的批次被重新处理。现入口先
  `check()`，已取消（含任一祖先被取消）的上下文直接抛 `Cancelled`，
  不再启动新调用。
