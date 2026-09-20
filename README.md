# deadletter

消息消费链路的进程内死信兜底，纯标准库，无外部依赖。

## 现状

`deadletter/queue.py` 提供 `DeadLetterQueue`：

- `DeadLetterQueue(handler, max_retries=3, clock=time.monotonic)`：handler 为注入消费者，正常返回视为成功、抛异常视为失败；max_retries 为进入死信前的连续失败上限；clock 为注入时钟
- `consume(msg)`：尝试消费一条消息，返回是否成功；失败未到上限只累计次数，达到上限移入死信区
- `dead()`：返回死信区快照（新列表，记录逐条复制），每条含 `msg` / `attempts` / `reason` / `dead_at`
- `retry_dead()`：把死信区每条消息再喂给 handler 一次，成功的移出、仍失败的留在原位，返回恢复条数
- 同一 id 一旦消费成功，失败计数清零；消息按原始 dict 传入，payload 不做拷贝
- handler 在锁外调用，多线程下单次操作安全，消费者回调重入不会死锁

## 新能力

- `DeadLetterQueue(..., retention=None, max_dead=None)`：可选的保留期（与 clock 同单位）与死信区容量上限
- `dead_groups()`：按失败原因分堆的快照 `{reason: [记录, ...]}`，每条含 `msg` / `attempts` / `reason` / `error` / `dead_at` / `last_at`
- `replay_group(reason)`：只重放某一堆；成功移出，仍失败退回原堆且 `attempts` 继续累加（不清零）
- `sweep_retention()`：把达到保留期的死信移入归档，返回归档条数（入队时也会先自动清一遍）
- `archived(reason=None)`：归档快照，可按组查询；记录额外带 `cause`（`ttl` / `capacity`）与 `archived_at`

## 问题

死信只按沉淀先后堆在一起，看不出失败门道；下游修好后只能整批重放，没修的会被反复折腾；死信还会一直占着内存，没有退出机制。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_queue.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 死信沉淀、分组重放、保留期与容量归档演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 分组键取沉底时异常的类型名（`type(exc).__name__`，即 `reason`）；重放即使抛出别的异常也退回原堆、键不变，只刷新 `error` 与 `last_at`。
- `replay_group(reason)` 按沉淀先后逐条重放：成功移出，仍失败时 `attempts` 在原值上 +1 继续累加，绝不重置，避免多轮重放后够不着窗口。
- 新死信入队的触发顺序：先跑保留期清理（`now - dead_at >= retention`，cause 为 `ttl`），再入队，最后超 `max_dead` 时从最老的逐条挪入归档（cause 为 `capacity`）。
- `sweep_retention()` 也可随时显式清理；`archived(reason=None)` 按组查询归档，全部快照均为逐条复制。
