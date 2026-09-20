# timeoutkit

调用编排层沉淀下来的小库：每次调用带预算，支持超时与取消传播，纯标准库，
无外部依赖。时钟可注入，便于测试。

## 模块说明

`timeoutkit/clock.py` 提供时钟抽象 `Clock`：

- `SystemClock`：进程默认时钟，`monotonic()` / `time()` / `sleep()`
- `FakeClock`：手动推进，`advance()` 推进真实时间，`jump_wall()` 只拨墙钟
  （模拟 NTP 校时），供测试注入

`timeoutkit/deadline.py` 提供 `Deadline(budget, clock)`：把相对预算换算成
单调钟上的绝对到期时刻，`remaining()` 给出剩余秒数，`expired()` 判断是否
耗尽。到期时刻锚定 `monotonic()`，墙钟被校时拨动不影响预算计量。

`timeoutkit/core.py` 提供 `CallContext` 与 `call`：

- `CallContext(clock=None, timeout=None, parent=None)`：调用上下文，携带预算、
  父子关系与取消状态
- `ctx.child(timeout=None)`：派生一个子上下文，用于限制下游步骤
- `ctx.remaining()` / `ctx.expired()`：查看剩余预算 / 是否耗尽
- `ctx.cancel()`：取消本上下文以及所有派生出来的子上下文
- `ctx.check()`：协作式取消点，被取消时抛 `Cancelled`
- `call(fn, timeout=None, ctx=None)`：在预算内执行 `fn`，超出预算抛 `Timeout`；
  未给 `ctx` 时按 `timeout` 新建根上下文；上下文与 `timeout` 同时给出时，
  取自身 `timeout` 与父级剩余预算中更紧的那个
- 子上下文（无论是否再给 `timeout`）都不能比父级活得更久：不给 `timeout`
  时直接继承父级截止时刻
- 已取消的上下文立即抛 `Cancelled`、已过期的上下文立即抛 `Timeout`，不会
  再发起新调用；等待期间父级取消会即时打断在途调用
- 调用超时（或 `ctx.check()` 发现预算耗尽）会取消其所在上下文及整棵子树，
  协作式下游步骤在自己的 `check()` 点即可及时停手；注意 `call(fn, ctx=...,
  timeout=...)` 的隐式子预算超时只作废该临时子上下文，不波及父级

`timeoutkit/__init__.py` 导出 `CallContext`、`call`、`Deadline`、`Cancelled`、
`Timeout` 以及三个时钟类。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## Known Issues

以下是早期版本在线上暴露过的问题，均已修复，对应回归用例见
`tests/test_regressions.py`：

1. **上游超时后下游写操作仍在后台执行，产生重复通知。**
   根因：`call()` 超时只对调用方抛出 `Timeout`，执行 `fn` 的 worker 线程
   并未被作废，上下文的取消标记也没有置位。worker 从不可中断的阻塞
   （如 `time.sleep`、同步 IO）醒来后，下一次 `ctx.check()` 仍看到“未
   取消”，于是把通知又写了一遍。修复：超时即取消调用所在上下文及其整棵
   子树，worker 在后续 `check()` 点会收到 `Cancelled` 而中止。Python 无法
   强杀线程，完全不调用 `check()` 的 `fn` 仍会跑完，这类下游需要自行做到
   协作式取消。

2. **父层给 800ms 预算、子调用自配 5s，子层跑满自己的节奏才停。**
   根因：`CallContext` 的截止时刻只由自己的 `timeout` 决定，派生子上下文
   时完全不看父级还剩多少预算；不给 `timeout` 的子上下文更是没有任何
   截止时刻。修复：子上下文构造时取“自身 timeout 换算出的截止时刻”和
   “父级截止时刻”中更早的一个，不给 `timeout` 时直接继承父级截止时刻，
   预算沿调用链只减不增。

3. **机房校时回拨墙钟时请求卡住，前跳时预算被提前掐断。**
   根因：`Deadline` 用墙钟 `clock.time()` 记录到期时刻并计算剩余预算，而
   墙钟会被 NTP 来回拨动——回拨时 `expires_at - now` 凭空变大（请求迟迟不
   到期），前跳时又凭空变小（尚有预算却被判超时）。修复：到期时刻与剩余
   计算全部改用单调钟 `clock.monotonic()`；`FakeClock.jump_wall()` 只动墙
   钟、不动单调钟，恰好用来回归验证这一点。

4. **拿已取消的上下文发起新调用照跑不误，作废的批次被重新处理。**
   根因：`call()` 在起 worker 线程前既不查 `cancelled` 也不查 `expired`，
   作废上下文与正常上下文一视同仁。修复：发起前先做预检——已取消抛
   `Cancelled`、已过期抛 `Timeout` 并取消上下文；worker 线程在真正执行
   `fn` 前还会再查一次，关掉“预检通过、线程开跑前被取消”的竞态窗口。

5. **父级取消后，在途调用要等自己的阻塞结束才有反应（无自身预算时甚至
   永不返回）。** 根因：`call()` 的等待只认 `job.done` 这一个事件，取消
   状态没人通知等待方。修复：上下文增加取消回调，`call()` 把回调注册进
   上下文，父级取消沿树传播时回调立即唤醒等待并抛 `Cancelled`；`check()`
   发现预算耗尽也会走同样的取消路径。
