# tickbase

压测工具里嵌的进程内任务调度器，纯标准库，无外部依赖。

## 现状

`tickbase/` 四个模块：

- `clock.py`：时间源。`SystemClock` 取系统时间，`ManualClock` 手动推进，测试和演示一律用它，不真的等待
- `triggers.py`：`IntervalTrigger(seconds)` 按间隔；`DailyTrigger(hour, minute, second)` 按本地时间每天固定时刻
- `executor.py`：派发方式。默认 `InlineExecutor` 当场执行，构造时可换带 `submit(fn)` 的执行器
- `scheduler.py`：`Scheduler(clock, executor, state_path=None)`，`add_task(name, trigger, fn, misfire="coalesce")` 注册，`poll()` 派发到点任务并返回任务名列表，`next_fire(name)` 查下一次计划触发时刻，`remove_task(name)` 注销，`flush()` 强制落盘，`stats()` 给 `runs`、`per_task` 与 misfire 的 `skipped`、`coalesced` 计数

任务函数收到的参数是计划触发时刻。注册后的第一次触发在一个触发周期之后。

## 目标

见任务描述。约束：

- `tests/test_scheduler.py` 是行为基线，一个字不许改，必须原样全绿
- 纯标准库，不引三方包

## 运行

```bash
python3 demo.py                              # 现状演示
python3 -m unittest discover -s tests -v     # 行为基线测试
```

## 实现说明

### 恢复口径

- 构造时传 `state_path`，每个任务的计划触发时刻（`next_fire`）会写进这个 JSON 文件：先写临时文件再 `os.replace` 原子替换，不会写出半截文件
- 落盘时机：`poll()` 结束时有变更就写；`flush()` 可强制写一次
- 重启后用同一个 `state_path` 起新 `Scheduler`，同名任务 `add_task` 时直接接上落盘的计划时间，不从当前时刻重排；状态文件只认任务名，不校验触发器，换了触发器就从恢复的点按新触发器继续走
- 状态文件不存在、是坏 JSON、只写了一半、或字段类型不对，一律当作空状态照常起来，新注册的任务从当前时刻起一个周期后首次触发
- `remove_task` 会同时摘掉落盘的状态

### 合并规则

- 下一次触发时刻一律按上一次计划时间沿网格往前推（`trigger.catch_up`），与 poll 时的时钟无关：任务跑多久都不带偏节奏，间隔任务也不会因为执行慢而漂移
- 停机或长任务错过多个计划点时，按任务的 `misfire` 策略处理：
  - `coalesce`（默认）：所有错过的点合并成一次补跑，任务函数拿到的是最早错过的那个计划时刻，补完回到原节奏；被合并掉的点数计进 `stats()["coalesced"]`
  - `skip`：错过的点直接丢掉、不补跑，下一次触发是严格晚于当前时刻的网格点；丢掉的点数计进 `stats()["skipped"]`
- 只到点一次（正常触发）不算 misfire，两种策略都照常派发、不计数
- 同一任务不允许两份并行：上一份没跑完时到点不派第二份，计划点挂起，等它跑完后按 misfire 策略结算

### 回拨防护

- 每个任务的 `next_fire` 只前进不后退，落盘的也是这个单调值
- 时钟往回拨时，已跑过的计划点早已越过，不会重跑、也不会补出一串触发风暴；回拨期间只是等待，时钟重新走过 `next_fire` 后按正常节奏继续

### 调度性能

- `poll()` 用最小堆（按 `next_fire` 排序，注册序号打破平局）只取到点的任务，不再每次全表扫描；派发的返回顺序仍是注册顺序
- 一万个任务、时钟按秒走一整天，几秒内跑完（见 `tests/test_misfire.py` 的性能用例）
