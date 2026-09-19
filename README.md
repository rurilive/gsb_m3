# mvstore

配置中心的单机 KV 存储，纯标准库，无外部依赖。

## 现状

`mvstore/store.py` 提供 `Store`：

- `Store(path=None)`：不给 path 纯内存；给了 path 所有写操作追加为 JSON 行日志，重新打开同一 path 按文件序重放恢复
- `get(key)`（不存在返回 None）/ `put(key, value)` / `delete(key)`（返回是否真的删了）
- value 为任意可 JSON 序列化对象
- 内部一把锁保护，多线程单操作安全

## 问题

没有事务：两个线程对同一 key 做读-改-写，互相整体覆盖，更新无声丢失。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_store.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 读写与恢复演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 快照：`begin()` 记下当前全局版本号作为快照，事务内 `get` 读该快照可见的最新版本，写操作只进私有缓冲
- 冲突判定：`commit` 时检查写集每个 key 的最后提交版本，若晚于本事务快照则抛 `ConflictError` 并作废（first-committer-wins）
- 版本推进：冲突检测通过后，全局版本号加一，缓冲写入逐个生效并记录 key 的最后提交版本，同时照旧追加 JSON 行日志
- `rollback` 直接丢弃缓冲并释放快照，不产生任何写入
- gc：保留所有活跃事务快照仍可见的版本，回收更早的旧版本；无活跃事务时每 key 只留最新版，已删除的 key 整体清除
