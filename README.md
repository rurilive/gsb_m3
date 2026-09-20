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

## 问题

死信只按沉淀先后堆在一起，看不出失败门道；下游修好后只能整批重放，没修的会被反复折腾；死信还会一直占着内存，没有退出机制。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_queue.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 死信沉淀与整体重放演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 分组键：失败异常的类名，即记录里的 `reason`；`groups()` 列出当前分组，`dead_group(group)` 取某一堆的快照（含 payload 与失败上下文）。
- 定向重放：`replay(group)` 只重放该组，成功的移出；仍失败的退回原组，`attempts` 累加 1 不清零，`reason`/`dead_at` 保持首次沉淀时的值。
- 保留期：`sweep()` 用注入时钟判定，`dead_at` 距今达到 `retention` 即归档（`cause="expired"`）。
- 容量：`sweep()` 在保留期清理之后执行，仍超 `capacity` 就从最老的开始归档（`cause="overflow"`）。
- 归档可查：归档记录附 `archived_at` 与 `cause`，`archived()` 全量、`archived(group)` 按组，均返回复制后的快照。
