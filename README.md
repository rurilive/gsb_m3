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
