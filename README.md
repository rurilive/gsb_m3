# hashring

把 key 稳定映射到节点的一致性哈希环，纯标准库，无外部依赖。

## 现状

hashring/ring.py 提供基础哈希环 HashRing：

- HashRing()：建立一个空环
- add_node(node)：把一个物理节点加入环，重复加入同一节点无副作用
- lookup(key)：返回 key 顺时针归属的节点，空环返回 None
- nodes()：环上的物理节点，按名字排序

每个物理节点当前在环上只占一个位置。

## 问题

单点环下节点负载很不均衡，节点增减时大量 key 无谓改归属，也无法按容量
给节点分配权重，更不能安全删除节点。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_ring.py 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
