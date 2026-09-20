# dedupq

消息接入服务里的本地去重队列，单进程内嵌，纯标准库，无外部依赖。

## 模块

- `dedupq/queue.py`
  - `DedupQueue(ttl=60.0, clock=None)`：内存去重队列
    - `submit(msg_id, payload=None)`：新 id 入队返回 True，重复 id 丢弃返回 False
    - `peek()`：返回队首 `(msg_id, payload)`，不消费；空队列返回 None
    - `pop()`：取出并消费队首，空队列返回 None
    - `size()` / `len()`：待消费条数
    - `cleanup()`：按当前时钟清理过期去重记录
  - `FakeClock`：可 `advance()` 的手动时钟，供演示与测试注入

去重记录保留 `ttl` 秒，过期后同一 id 可再次入队。默认时钟为 `time.monotonic`。

## 运行

```bash
python3 demo.py
```

## Known Issues

以下问题已在当前版本修复，记录现象与根因备查：

1. **重复消费**：一笔消息处理完后，上游重投同 id 又被放行，下游重跑。
   根因：`pop()` 消费时顺手 `del self._seen[msg_id]`，去重记录随消费立即失效，
   TTL 内的重投被当成新消息。修复：去重记录只按 TTL 过期，消费不再删除。
2. **内存只涨不落**：进程内存持续增长，重启才回落。
   根因：`self._payload` 只写不删——`pop()` 不清理已消费消息的载荷，
   `_cleanup()` 也只清 `_seen` 不清 `_payload`，载荷永久堆积。
   修复：`pop()` 用 `self._payload.pop(msg_id, None)` 随消费移除载荷。
3. **多实例互相串扰**：两个 worker 各自 `new` 队列，A 放行过的 id 到 B 被静默当重复丢弃。
   根因：`__init__(self, ..., _seen={})` 使用可变默认参数，
   所有实例共享同一个 `_seen` 字典。修复：默认改为 `None`，每个实例独立建表。
4. **空载荷消息 pop 抛异常**：心跳类消息不带载荷，消费到它时 `pop()` 抛 `KeyError`，
   消费线程挂掉、后续消息全堵住。
   根因：`submit()` 对 `payload=None` 不写入 `_payload`，而 `pop()` 用
   `self._payload[msg_id]` 硬取。修复：`pop()` 改用 `.pop(msg_id, None)`，
   无载荷返回 `(msg_id, None)`。
