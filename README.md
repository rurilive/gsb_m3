# segpile

分段存储引擎，纯标准库，无外部依赖。写热点数据的小引擎，段越滚越多，
靠合并回收空间。

## 包结构

- `segpile/device.py`：`SimDevice`，IO 设备兼模型时钟。`charge()` 是调用方
  自己用设备，同步等设备空出来；`reserve()` 是后台把设备占住一段时间，
  只占设备、不推进前台时钟。`advance()` 手动推时钟，测试靠它复现时间轴。
- `segpile/segment.py`：`Segment` 一段只读日志，段内按键有序；`merge_pairs()`
  按键归并若干段，后来的盖住先来的；`merge_units()` 算一次归并的 IO 规模。
- `segpile/backend.py`：`MemoryBackend`，段 blob 加一份 meta 文档的落盘口子，
  读出去的都是副本。
- `segpile/store.py`：`Store` 引擎本体，写入、滚段、查询、`compact_once()`。
- `segpile/scheduler.py`：`Scheduler` 后台压缩调度，按预算分轮执行合并，
  带段锁、公平性和崩溃恢复。

## 用法

```python
from segpile import MemoryBackend, SimDevice, Store

device = SimDevice()
store = Store(MemoryBackend(), device, segment_limit=8)

latency = store.put("user:1", "alice")   # 返回这次前台写的耗时
store.get("user:1")

store.compact_once()                     # 手动压一轮，挑最小的相邻两段并成一段
```

后台压缩：

```python
from segpile import Scheduler

sched = Scheduler(store, budget=4)       # 每轮最多占 4 个 IO 单位
sched.step()                             # 推进一轮，合并收尾时返回 CompactReport
```

## 口径

- 段的新旧按 `(seq, sid)` 比，越新越能压住旧值；合并结果沿用最新输入那段
  的 sid 和 seq（`compact_once`），段之间的新旧关系不会因为合并变化。
  后台调度的合并为了崩溃可恢复，输出写进全新 sid，但 seq 沿用最新输入
  那段，新旧关系同样不变。
- 只有 `(seq, sid)` 序上相邻的两段能并：隔着别的段硬并，旧 key 会跳过
  中间段里的新值复活。
- 活动段可以继续追加，不参与压缩。
- 每次滚段、合并都会重写 meta；重新 `Store(同一份 backend)` 就是重启后的样子。
- 后台合并先写 journal 再动手，最后一步才改段清单；重启时没做完的合并
  会被认出来：输出已落盘就前滚补完，没落盘就等新的 `Scheduler` 接着做。
- IO 单位：追加一条算一个写单位，合并读的是输入段大小之和，写的是结果段
  的大小，另外每轮写 meta 算一个单位。

## 运行

```bash
python3 demo.py                           # 滚段、手动压缩、写峰期延迟
python3 -m unittest discover -s tests -v  # 行为基线
```
