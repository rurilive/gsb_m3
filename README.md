# txnkit

进程内键值存储与事务，纯标准库，单线程模型，无外部依赖。

## 现状

`txnkit/store.py` 提供两个入口：

- `KVStore(initial=None)`：`set(key, value)` / `get(key, default=None)` /
  `delete(key)`（返回是否删掉）/ `keys()`；`begin()` 开启一个事务
- `Transaction`：`get` / `set` / `delete`，`commit()` 提交，`rollback()` 回滚；
  事务关闭后再调用会抛 `RuntimeError`
- `ConflictError`：提交时发现键在事务开始后被其他事务改过时抛出，约定见任务描述
- 事务开始时给主表拍一份快照，事务内的读走快照，写入先记在写集合里，
  提交时并回主表；每个键带一个版本号，本来是为提交时的冲突检测准备的

## 问题

联调环境里事务的隔离性对不上：事务内写进去的值自己读不到；提交后外面改动
传进去的那个对象会影响存储；回滚之后被删掉的键没回来；两个事务先后提交时，
先提交的结果会被后一个冲掉。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_store.py` 基线保持不变（基线一个字不改）
- 纯标准库
- `python3 demo.py` 能直接跑通

## 运行

```bash
python3 demo.py                          # 五个隔离场景演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
