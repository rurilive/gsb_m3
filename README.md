# timectl

纯标准库的定时器调度器雏形，无外部依赖。

## 现状

`timectl/timer.py` 提供 `LoopTimer`，一个同步循环触发的定时器：

- `LoopTimer(clock=None)`：clock 可注入，默认 `time.monotonic`
- `register(delay, cb)`：挂 delay 秒后触发的一次性任务，返回句柄，delay 需为正
- `tick(now)`：把时钟推进到 now，按到期顺序同步调用回调，返回本轮触发的句柄
- `cancel(handle)`：取消任务，已取消或已触发的返回 `False`
- `now`、`size`：当前时钟与待触发任务数

只有「延迟一次」这一种语义，回调在 `tick` 里当场同步执行。

## 问题

短时间内的连打会被原样放大成同样多次回调，前端输入、按钮连点、事件抖动这类
场景完全扛不住；没有周期任务，要周期性触发只能自己反复注册；也没有统一的到点
排序与取消回收口径，多个来源的任务混在一起推进时先后顺序无从保证。

## 目标

在现有基础上补出防抖、节流、延迟与周期任务统一的定时器调度器，见任务描述。约束：

- 现有行为与 `tests/test_loop.py` 基线保持一致（基线一个字不改）
- 新行为另开 `tests/test_timer.py`
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
