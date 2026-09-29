# shardmap

一个映射容器，纯标准库，无外部依赖。

## 现状

shardmap/map.py 提供最朴素的单字典映射 FlatMap：

- FlatMap()：建立一个空映射
- get(key, default=None)：按键取值，缺失返回 default
- set(key, value)：写入或覆盖
- delete(key)：删除并返回是否删到
- in / len / keys() / items()：包含、长度与快照式视图
- snapshot()：返回当前内容的字典副本

所有读写都直接落在一个内建字典上，没有分片、没有锁、没有并发保护。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_map.py 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
