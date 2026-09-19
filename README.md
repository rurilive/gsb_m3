# delayq

任务编排平台的延时队列，heapq 实现，时钟注入，纯标准库，无外部依赖。

## 模块说明

`delayq/queue.py` 提供延时队列 `DelayedQueue(clock=None)`：

- `add(task, delay, key=None)`：任务在 delay 秒后到期；key 相同的重复
  提交以最后一次为准，旧条目作废，不会被再次执行
- `pop_ready()`：只弹出已到期（due <= 当前时刻）的任务；同一时刻到期
  的任务按提交顺序出队；没有到期任务时返回 None
- `peek()`：距最近到期任务的等待秒数，消费端按它睡眠后再轮询；队列
  为空返回 None
- `len(q)`：当前排队条目数

`delayq/clock.py` 提供时钟抽象：`SystemClock` 为进程默认时钟，
`FakeClock` 支持 `advance()` / `jump_to()` 手动推进，供测试注入。

## 运行

```bash
python3 demo.py
```

## Known Issues
