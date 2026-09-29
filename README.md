# shardmap

进程内并发哈希表，纯标准库，无外部依赖。

## 现状

`shardmap/hashmap.py` 提供单锁哈希表 `ConcurrentHashMap`：

- `ConcurrentHashMap(capacity=8, hash_fn=None, clock=None)`：capacity 是桶数，hash_fn 是可注入的哈希函数，缺省用内置 `hash`
- `get(key, default=None)` / `put(key, value)` / `delete(key)` / `contains(key)`
- `size`：当前键值对数；`keys()` / `items()`：当前内容的快照列表
- `depth`：并行度口径，单锁实现下恒为 1
- 内部一把可重入锁保护全部桶，多线程读写安全

## 问题

所有操作共用一把锁，任何写都会挡住全部读，键规模与并发度上来之后锁竞争成为瓶颈。
表满之后只能挂链，没有扩容，长链把查找拖成线性；遍历时也没有稳定的迭代口径。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_hashmap.py` 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
