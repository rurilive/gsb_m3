# ordix

内存里的有序索引，纯标准库，无外部依赖。眼下只有一个单线程的
B+ 树，服务的读写都走同一个进程、同一个线程。

## 现状

`ordix/tree.py` 提供 `BPlusTree(min_degree=3, pool=None)`：

- `put(key, value)`：插入或覆盖，返回是否新插入
- `get(key)`：查不到返回 None；`contains(key)` 是它的布尔版
- `delete(key)`：返回是否真的删掉了
- `scan(start=None, stop=None)`：升序遍历 `[start, stop)`，返回惰性迭代器
- `len(t)`：键数；`height()`：树高
- `stats()`：puts / gets / hits / misses / deletes / removed / scans /
  splits / merges / borrows 计数快照，外加 size 与 height
- `pool_stats()`：节点池计数，`live` 是当前还被占用的节点数
- `validate()`：结构自检，坏了抛 `InvariantError`

结构约定：

- 最小度数 t 由 `min_degree` 给，非根节点最多 2t-1 个键、最少 t-1 个
- 数据只在叶子里，叶子用 `next` 串成升序链，`scan` 顺着链走
- 内部节点有 c 个孩子、c-1 个键，第 i 个键是第 i+1 个孩子子树的
  最小键，`_min_key` 顺着 `children[0]` 下到叶子才能拿到
- 分裂、借用、合并都发生在写入路径上；删除把空出来的节点还给池子，
  复用前必须过一遍 `nodes.reset`

`ordix/pool.py` 的 `NodePool` 只管对象的复用与计数，`release` 只挂回
空闲链、不清内容，`live` 等于 acquire 次数减 release 次数。目前没有任何
锁，多线程同时读写同一棵树不在支持范围内。

## 运行

```bash
python3 demo.py                           # 写入、扫描、删除与回收演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```

## 目录

- `ordix/nodes.py`：节点结构与 `reset`
- `ordix/pool.py`：节点池与计数
- `ordix/tree.py`：`BPlusTree`
- `tests/test_tree.py`：行为基线
- `demo.py`：跑一遍给人看的脚本
