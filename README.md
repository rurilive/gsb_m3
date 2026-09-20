# skiplist

检索侧内存有序映射，跳表实现，纯标准库。键为同类型可比较值（demo 用整数），
value 任意。非线程安全。构造时可传 `seed` 复现随机层级。

## 语义约定（以下为本模块的正式行为定义）

1. **insert(key, value)**：**恒新增一个副本，不覆盖既有副本**；同键副本按插入先后共存于链上，先插的在前。
2. **remove(key)**：存在副本时**恰移除最旧的一个并返回 True**；没有副本则返回 False，且不改动任何结构。移除之后，该键若已无副本，`__contains__` 必须为 False，range_scan 也不再输出它。
3. **find(key) / `in`**：存在任一副本即命中；find 返回最旧副本的 value，无副本返回 None。
4. **`len()`**：**等于副本总数**，与 `range_scan()` 的输出条数一致。
5. **range_scan(lo=None, hi=None)**：**闭区间 [lo, hi]**，按 key 非降序输出每个副本的 `(key, value)` 元组；lo/hi 为 None 表示该侧无界；lo 大于 hi 时返回空列表。
6. **层级分布**：新节点高度从 1 层起，每层以 1/4 概率再升一层，即 P(height ≥ k) = (1/4)^(k-1)，上限 16 层。**`max_height` 属性返回当前最大节点高度（空表为 0），供诊断用**；千级元素规模下 max_height 通常不低于 4 层。
7. 查找/插入/删除的 O(log n) 依赖第 6 条的分布成立。

## 运行

```bash
python3 demo.py
```

## 测试报告

测试位于 `tests/test_skiplist.py`（标准库 unittest，固定 seed，可独立重复运行）：

```bash
python3 -m unittest discover -s tests -v
```

共 21 个用例：13 绿、8 红。红用例对应 4 处源码与 README 的出入：

- **`test_max_height_at_thousand_scale`、`test_no_superlinear_scaling`**：`_random_height` 循环条件误写为 `h > _MAX_LEVEL`（应为 `h < _MAX_LEVEL`），所有节点恒为 1 层，违反第 6 条层级分布，查找/插入退化为 O(n)（第 7 条不成立，1e4→1e5 每操作耗时约 10 倍）。修复方向：把循环条件改回 `h < _MAX_LEVEL`。
- **`test_remove_unlinks_key`、`test_remove_only_oldest_copy`**：`remove` 只记录并摘除 1 层及以上的前驱链接，从不摘除第 0 层，返回 True 且 len 减一，但节点仍挂在底链上——已删键在 find/range_scan 中「冒出来」，违反第 2 条。修复方向：remove 时记录第 0 层前驱并一并摘除（复用 `_preds` 即可）。
- **`test_duplicate_copies_coexist_in_insertion_order`、`test_len_counts_each_copy_once`**：重复键插入时 `_splice` 因 `pred.key == node.key` 跳过第 0 层链接，副本根本没入链；同时重复分支内 `self._size += 1` 与末尾的 `+= 1` 重复计数，违反第 1、4 条。修复方向：删掉分支内多算的 `+= 1`，并让副本在同键段末尾正常链接（去掉 `_splice` 的同键跳过或改为定位到段尾后链接）。
- **`test_contains_with_none_value`**：`__contains__` 用 `find(key) is not None` 判断，存入 None 值的键被误判为不存在，违反第 3 条「存在任一副本即命中」。修复方向：`__contains__` 改为直接做存在性判断，不依赖 value 非 None。

对拍用例 `test_random_op_stream_matches_reference`（3000 步固定 seed 随机操作流，对照朴素参考实现）同样因上述缺陷分叉而红，可作为修复后的整体回归。
