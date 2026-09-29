# mvvault

单机版本化内存 KV：每次写入留一个带提交时间戳的版本，读取按时间戳挑可见版本，
纯标准库，无外部依赖。

## 现状

mvvault/store.py 提供 MVStore 与 Version：

- MVStore()：一个键到版本链的映射，提交时间戳由内部单调计数分配，从 1 起
- put(key, value)：追加一个普通版本，返回它的提交时间戳
- delete(key)：追加一条删除墓碑版本，返回该键此前是否存在
- get(key)：返回键当前可见的值，键不存在或已删返回 None
- keys()：当前存在的键，按升序
- latest_ts：已分配的最大提交时间戳，空 store 为 0
- Version：namedtuple(ts, value, deleted)，一条版本记录
- 每个键的版本链按提交时间戳升序，所有读写在一把可重入锁下进行

## 问题

只有当前读，读不到写之前的历史值；没有快照，读-改-写序列之间没有隔离，
后来者会覆盖先来者；同键并发写没有冲突检测，谁后写谁说了算；
旧版本只增不减，长跑下来内存只涨不落；也取不到单个键的历史版本。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_store.py 基线一致（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
