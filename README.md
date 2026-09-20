# mvstore

配置中心的单机 KV 存储，纯标准库，无外部依赖。

## 现状

`mvstore/store.py` 提供 `Store`：

- `Store(path=None)`：不给 path 纯内存；给了 path 所有写操作追加为 JSON 行日志，重新打开同一 path 按文件序重放恢复
- `get(key)`（不存在返回 None）/ `put(key, value)` / `delete(key)`（返回是否真的删了）
- value 为任意可 JSON 序列化对象
- 内部一把锁保护，多线程单操作安全
- MVCC 事务：`begin()` 返回事务；事务内 `get/put/delete`；`commit()` 冲突时抛 `ConflictError`，`rollback()` 丢弃缓冲；也支持 `with store.begin() as txn`

## 解决的问题

两个线程对同一 key 做读-改-写时，快照隔离 + first-committer-wins 冲突检测保证更新不会无声丢失：后提交者收到 `ConflictError` 并整体作废，可用新事务重试。

约束：

- 现有方法行为与 `tests/test_store.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 读写与恢复演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 每个 key 一条版本链 `(version, value)`，删除以墓碑表示；全局版本号每次成功提交（含单操作自动提交）加一，另记每个 key 的最后提交版本。
- `begin()` 记录当前全局版本作为快照：事务 `get` 只读取版本号不大于快照的最新条目，写操作先放写集缓冲，读时缓冲优先。
- `commit()` 对写集逐个比对：某 key 的最后提交版本大于本事务快照版本即抛 `ConflictError`，事务作废、缓冲不生效；否则写集以同一新版本整体生效。
- 同一版本内的写入按写集顺序追加 JSON 行日志（`put`/`del`），重启重放重建版本链。
- `gc()` 取所有活跃事务快照版本的最小值，删除严格更旧的版本；无活跃事务时每个 key 只留最新版（墓碑也保留）。
