# winagg

规则引擎的进程内事件指标聚合，纯标准库，无外部依赖。

## 现状

`winagg/window.py` 提供 `EventCounter`：

- `EventCounter(clock=time.monotonic)`：clock 为注入时钟，用来记事件的到达时刻
- `add(ts, v=1)`：记一个事件，ts 为事件时间，v 为计数增量，返回累计总和
- `total()`：已记录事件的计数总和；`count()`：已记录事件条数
- `span()`：已记录事件的时间跨度 `(最早, 最晚)`，没有事件时返回 None
- `last_arrival()`：最近一次 add 的到达时刻，没有事件时返回 None
- `reset()`：清空全部事件与计数
- 事件时间不要求递增，乱序到达原样入账，增量允许为负
- 事件按到达顺序存在列表里，只追加不淘汰；内部一把锁，多线程单操作安全

## 问题

事件只加不减，线上跑久了内存一路涨；也没有只看最近一段时间的口径，迟到的事件混进来更分不清该不该算。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_window.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 累计计数演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明（滑动窗口）

- `winagg/sliding.py` 提供 `WindowedCounter`（单窗口）与 `MultiWindowCounter`（多窗口并行）
- 窗口区间取闭开 `[start, end)`：起点计入，恰好落在右边界的归下一个窗口
- 水位线取历史最大事件时间，只增不减；窗口随水位线推进关闭，与到达时刻无关，重放可复现
- 任意时刻至多一个开口窗口，关闭即淘汰，内存有界；迟到但落在开口窗口内的事件照常计入
- 早于左边界（窗口已关闭）的事件按 `late_policy` 处理：`"drop"` 丢弃、`"count"` 计入 `late_total`，两种都记 `late_count`
- 窗口关闭时聚合结果作为 `ClosedWindow(start, end, total)` 记入产出缓冲（可配 `keep_outputs` 与 `on_close` 回调），离线补数可捞
- `merge(a, b)` 合并相邻已关闭窗口，仅当两条都在缓冲内（未过期）且时间连续（`a.end == b.start`）时允许
- 多窗口各自维护独立水位线与淘汰，短窗口到点先关闭，互不影响
