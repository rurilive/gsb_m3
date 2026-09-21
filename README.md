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

- `winagg/sliding.py`：`SlidingWindow(length, on_late=, closed_retention=, clock=)` 查最近 N 秒计数和；`MultiWindow(lengths, ...)` 同一份数据并行多个长度
- 窗口只随事件时间推进：watermark = 已见最大事件时间，注入时钟仅给产出盖关闭时刻，重放历史数据结果可复现
- 边界取闭开：滚动桶为 `[start, end)`，边界点归右侧桶；滑动窗口左边界含端点（`ts >= watermark - length` 计入）
- 乱序判定：`ts < watermark - length` 判迟到，`on_late="drop"` 丢弃并记 `late_count()/late_total()`，`"raise"` 抛 `LateEventError`，不默默吞
- 淘汰是物理删除：watermark 前进时窗口外事件从有序队列移除，内存随窗口有界，不是查时装作看不见
- 被挤出窗口的桶聚合成 `ClosedWindow(start, end, total, count, closed_at)` 产出，`drain_closed()` 供离线补数捞取
- `merge_closed(a, b)` 合并相邻已关闭窗口，仅当时间连续（`a.end == b.start`）且都未过期（`closed_retention` 内未被清除）时允许
- 多窗口各扫各的：每个 `SlidingWindow` 独立维护自己的 watermark、事件队列与淘汰，短窗口到点先走
