# tracectx

批处理作业里的跨线程执行小工具：批量并发、后台单任务、并发闸门。纯标准库，无外部依赖。

## 模块

- `tracectx/batch.py` — `map_batch(fn, items, workers=4)`：切片并发处理，结果与输入同序；单条失败放 `ItemFailure(item, error)` 占位，不拖垮整批；`first_failure(results)` 取第一个失败
- `tracectx/detached.py` — `run_detached(fn, *args, timeout=None)`：后台线程执行，异常原样重抛，超时抛 `TimeoutError`；`async_call(fn, *args, on_done=None, on_error=None)`：回调式 fire-and-forget，返回线程句柄
- `tracectx/gate.py` — `Gate(max_active)`：并发上限闸门，`enter(timeout)` / `leave`，也可作上下文管理器
- `tracectx/tracing.py` — 跨线程调用链上下文：`trace_session` / `span` 计时、`TracedThread` 与 `TracedThreadPoolExecutor` 包装器、`format_tree` 树形报告

## 约定

- 各模块的接口与语义以 docstring 为准，行为基线见 `tests/`。
- 纯标准库，Python 3.8+。

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 上下文语义

### id 传播

- 一条链路从 `trace_session(name, cid=None, slow_threshold=...)` 开始：不传 `cid` 时由 `new_cid()` 生成形如 `cid-xxxxxxxxxxxx` 的 id；会话内 `current_cid()` 可取当前链路 id，会话外为 `None`，退出会话自动恢复。
- 上下文基于 `contextvars`，只在边界处快照迁移：`TracedThread` 在 `start()` 时快照提交方的当前上下文（correlation-id 与当前 span），`TracedThreadPoolExecutor.submit()` 同样在提交时快照。因此包出来的任务自动带上提交方的链路 id，多个并发链路 / 线程各持独立快照，链路之间互不串号；线程内新建的会话或修改不会回漏到提交方。
- `map_batch`、`run_detached`、`async_call` 的工作线程已统一走 `TracedThread`，在这些执行层里创建的 span 自动归属提交方链路；未显式开会话时，裸用 `span()` 会临时生成一个 id，块结束即恢复。

### span 嵌套

- span 带 `name`，用 `time.monotonic()` 计时，作为上下文管理器使用（`with span("x") as s:`），异常抛出时也会正常收尾，`s.elapsed` 是该段耗时。
- 子 span 在 `__enter__` 时挂到当前 span 下，`level` 按深度递增；由于快照里带着提交方的当前 span，工作线程里开的 span 会跨线程归位到提交方 span 之下，并发挂接有锁保护，顺序为提交（启动）顺序。
- 一条链路的根 span 即 `trace_session` 的 `.root`，退出会话后用 `root.to_tree()`（或 `format_tree(root)`）一次打印整棵树；每行按层级缩进，含 name、耗时（不足 1 秒显示 `ms`）、慢标记。

### 慢阈值行为

- 阈值单位为秒，判定规则是耗时**严格大于**阈值才打慢标记（`elapsed > threshold`），等于阈值不算慢。
- `trace_session(..., slow_threshold=0.1)` 为整条链路设默认阈值（模块默认 `DEFAULT_SLOW_THRESHOLD = 0.1`）；`span("x", slow_threshold=...)` 可对单段覆盖，缺省时继承父 span 的阈值。传 `float("inf")` 等极大值可让某段永不打慢，根 span 自身也按同一规则参与判定（慢子段会让根也变慢）。
