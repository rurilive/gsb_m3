# tickbase

压测工具里嵌的进程内任务调度器，纯标准库，无外部依赖。

## 现状

`tickbase/` 四个模块：

- `clock.py`：时间源。`SystemClock` 取系统时间，`ManualClock` 手动推进，测试和演示一律用它，不真的等待
- `triggers.py`：`IntervalTrigger(seconds)` 按间隔；`DailyTrigger(hour, minute, second)` 按本地时间每天固定时刻
- `executor.py`：派发方式。默认 `InlineExecutor` 当场执行，构造时可换带 `submit(fn)` 的执行器
- `scheduler.py`：`Scheduler(clock, executor)`，`add_task(name, trigger, fn)` 注册，`poll()` 派发到点任务并返回任务名列表，`next_fire(name)` 查下一次计划触发时刻，`remove_task(name)` 注销，`stats()` 给 `runs` 与 `per_task` 计数

任务函数收到的参数是计划触发时刻。注册后的第一次触发在一个触发周期之后。

## 已知限制

- 任务状态只在进程内，进程重启后全丢，得重新注册
- 每次 `poll()` 会把所有任务过一遍
- 到点的判定和下一次触发时刻的重算都以 poll 当时的时钟为准

## 目标

见任务描述。约束：

- `tests/test_scheduler.py` 是行为基线，一个字不许改，必须原样全绿
- 纯标准库，不引三方包

## 运行

```bash
python3 demo.py                              # 现状演示
python3 -m unittest discover -s tests -v     # 行为基线测试
```
