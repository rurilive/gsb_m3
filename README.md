# mvstore

配置中心的单机 KV 存储，纯标准库，无外部依赖。

## 用法

`mvstore/store.py` 提供 `Store`：

- `Store(path=None)`：不给 path 纯内存；给了 path 所有写操作追加为 JSON 行日志，重新打开同一 path 按文件序重放恢复
- `get(key)`（不存在返回 None）/ `put(key, value)` / `delete(key)`（返回是否真的删了）
- value 为任意可 JSON 序列化对象
- 内部一把锁保护，多线程单操作安全
- `begin()` 返回事务：`get` 读快照、`put`/`delete` 缓冲、`commit()` 冲突时抛 `ConflictError`、`rollback()` 放弃；也支持 `with store.begin() as tx`

## 约束

- 现有方法行为与 `tests/test_store.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 读写与恢复演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 每 key 维护按版本号升序的版本链（普通值或删除墓碑）；`begin()` 记下当时全局版本，事务 `get` 只读版本号 ≤ 快照版本的最新条目，`put`/`delete` 仅进本地缓冲（读时可见自己的缓冲）
- commit 在锁内检查写集：任一 key 的最后提交版本 > 本事务快照版本，即抛 `ConflictError` 并作废事务，实现 first-committer-wins
- 无冲突则全局版本号 +1，写集全部落到该新版本并更新各 key 最后提交版本，再逐行追加 JSON 行日志（记录带 `version`）；rollback 只丢弃缓冲，不推进版本
- `gc()` 收集所有活跃事务的快照版本（外加当前全局版本供自动提交读），每 key 仅保留这些快照各自可见的最新版本条目，其余回收
- 无活跃事务时每 key 只留最新版（删除墓碑也保留，`get` 仍返回 None）；key 的最后提交版本元数据任何时候都不回收
