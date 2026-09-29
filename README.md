# hashring

把 key 分配到节点的分片器，纯标准库，无外部依赖。

## 现状

hashring/ring.py 提供一个最朴素的取模分片器 ModShard：

- ModShard()：建立一个空分片器
- add_node(node)：把一个物理节点加入分片器，重复加入同一节点无副作用
- owner(key)：返回 key 归属的节点，按 key 哈希对节点数取模，空分片器返回 None
- nodes()：分片器上的物理节点，按名字排序

没有环、没有虚拟节点、没有副本，也不支持删除节点。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_ring.py 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
