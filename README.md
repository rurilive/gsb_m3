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

- 快照：`begin()` 记下当前全局版本号作为快照版本，`get` 返回快照可见的最新版本（写缓冲优先，read-your-writes）
- 版本存储：每 key 存 `(提交版本, 值)` 升序列表，删除用墓碑标记；另记每 key 最后提交版本，gc 不清
- 冲突判定：`commit` 时写集中任一 key 的最后提交版本大于快照版本，即被他人改过，抛 `ConflictError` 并作废事务（first-committer-wins）
- 版本推进：检测通过后全局版本号加一，写集整体以该新版本生效，并照旧追加 JSON 行日志
- gc：保留每 key 最新版本及每个活跃事务快照可见的版本，其余回收；无活跃事务时每 key 只剩最新版
