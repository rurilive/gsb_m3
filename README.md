# tracectx

批处理作业里的跨线程执行小工具：批量并发、后台单任务、并发闸门。纯标准库，无外部依赖。

## 模块

- `tracectx/batch.py` — `map_batch(fn, items, workers=4)`：切片并发处理，结果与输入同序；单条失败放 `ItemFailure(item, error)` 占位，不拖垮整批；`first_failure(results)` 取第一个失败
- `tracectx/detached.py` — `run_detached(fn, *args, timeout=None)`：后台线程执行，异常原样重抛，超时抛 `TimeoutError`；`async_call(fn, *args, on_done=None, on_error=None)`：回调式 fire-and-forget，返回线程句柄
- `tracectx/gate.py` — `Gate(max_active)`：并发上限闸门，`enter(timeout)` / `leave`，也可作上下文管理器
- `tracectx/trace.py` — 跨线程调用链上下文：`start_trace()` 开链路，`span(name)` 嵌套计时，`TracedThread` / `TracedThreadPoolExecutor` 传播上下文，`format_report()` / `print_report()` 输出树形报告

## 约定

- 各模块的接口与语义以 docstring 为准，行为基线见 `tests/`。
- 纯标准库，Python 3.8+。

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 上下文语义

- **id 传播**：`start_trace()` 在入口生成 correlation-id（也可显式传入），存入 `contextvars`；`TracedThread`、`TracedThreadPoolExecutor` 以及 `map_batch` / `run_detached` / `async_call` 内部起的线程都会复制提交时的上下文，任务里 `current_correlation_id()` 拿到的仍是入口那条链路的 id。每条链路有独立的上下文副本，并发链路互不串号；不在任何链路里时返回 `None`。
- **span 嵌套**：`span(name)` 用 `time.monotonic()` 计时，`with` 嵌套时子 span 自动挂到当前 span 的 `children` 下；跨线程时子 span 依然归位到上下文被复制那一刻的当前 span 上，整棵树不会因为换线程而散掉。span 对象上可读 `duration`（秒）、`parent`、`children`、`slow`。
- **慢阈值**：阈值以秒计，`start_trace(slow_threshold=...)` 按链路配置，缺省用模块级默认（0.5s，可用 `set_slow_threshold()` 改）。span 结束时耗时超过阈值即标记为慢，`format_report()` / `print_report()` 输出的树形报告里对应行带 `[SLOW]` 后缀；报告按嵌套层级缩进，每行含 name、耗时（ms）、慢标记，收尾一次打出整棵树。
