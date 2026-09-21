# membersim

调度器的集群成员管理沙盘，纯标准库。节点、时钟、网络全在进程里
模拟，节点之间靠内存对象传消息，测试不碰真实网络。

## 目录

- `membersim/clock.py`：`SimClock`，可手动推进的虚拟时钟
- `membersim/network.py`：`InMemoryNetwork`，进程内消息队列，丢包、延迟、乱序、分区可注入
- `membersim/member.py`：`MembershipTable`，节点本地的成员表
- `membersim/node.py`：`Node`，持有成员表，通过注入的网络收发消息
- `membersim/cluster.py`：`Cluster`，把节点和时间线拼起来，`step()` 推进一个周期
- `membersim/reference.py`：`TrueSchedule`，上帝视角的真实存活时间线，对拍基准
- `membersim/scenarios.py`：按固定种子生成随机时间线，`apply_event` 负责回放

## 约定

- 消息就是普通 Python 对象。`Node.on_message(src, payload)` 按
  `payload[0]` 分发，目前只有 `"table"` 一种整表快照
- 每个周期 `Cluster` 调一次 `Node.on_period(period)`，崩掉的节点不调
- 投递给崩掉节点的消息会丢；断链期间到期的消息也会丢，不会攒着
- 同一对节点之间不保证先进先出
- 随机源和时钟都从外部注入，同一种子跑出来的时间线完全可复现
- 单线程使用，节点里没有锁

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
