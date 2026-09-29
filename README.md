# idkit

分布式 ID 生成器的现有实现，纯标准库，无外部依赖。

## 现状

`idkit/snowflake.py` 提供 `SnowflakeGenerator`：

- 构造函数 `SnowflakeGenerator(node_id=0, clock=None)`，`node_id` 取值 `0..MAX_NODE`，`clock` 是返回当前毫秒的可调用对象，缺省用系统时钟
- `next_id(now_ms=None)`：生成下一个 ID。时间戳前进则序列号归零，时间戳不变则序列号加一
- `compose(timestamp, node_id, sequence)`：按位拼装 ID
- `parse(value)`：反解出 `(timestamp, node_id, sequence)`
- `node_id` 与 `last_timestamp` 只读属性

位布局：低 `SEQUENCE_BITS` 位是序列号，往上是 `NODE_BITS` 位节点号，再往上是相对 `EPOCH_MS` 的毫秒时间戳。常量 `EPOCH_MS`、`SEQUENCE_BITS=12`、`NODE_BITS=10` 均可从包直接 import。

异常：`IdError` 为基类；同一毫秒序列号用尽抛 `SequenceExhausted`；检测到时钟回拨抛 `ClockBackwards`。

## 问题

现有实现每次只出一个 ID，且对时钟回拨只有一种反应（直接抛错），同一毫秒序列号用尽也只是抛错而不尝试等待。没有一次性取一批 ID 的入口，也没有可切换的回拨处置策略。

## 目标

见任务描述。约束：

- `tests/test_snowflake.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 连续生成与反解演示
python3 -m unittest discover -s tests -v # 行为基线测试
```