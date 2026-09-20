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

测试位于 `tests/test_skiplist.py`（纯标准库 unittest），运行方式：

```bash
python3 tests/test_skiplist.py          # 或 python3 -m unittest tests.test_skiplist
```

当前共 33 个用例：17 绿、16 红（红即钉住源码与本 README 的出入）。
所有随机数据均用固定 seed，统计性断言留有宽余量，整套可独立重复运行
（约 12 秒；其中性能用例因源码缺陷在 2 万键检查点即提前失败）。
用一份修正全部缺陷的跳表实现替换 `SkipList` 后，33 个用例全部转绿。

红用例对应的源码缺陷（括号内为代表用例）与建议修复方向：

1. **层级随机永远只产生 1 层**（`test_red_geometric_tail_probabilities`、
   `test_red_cap_can_actually_be_reached`、
   `test_red_max_height_grows_beyond_one_at_thousand_scale`）：
   `_random_height` 循环条件误写为 `while h > _MAX_LEVEL`，恒为假。
   建议改为 `while h < _MAX_LEVEL and self._rng.random() < _P`。
2. **同键新副本接不上链（链外孤儿）**（
   `test_red_duplicate_insert_creates_coexisting_copies`、
   `test_red_three_copies_ordered_oldest_first`、
   `test_red_find_sees_second_copy_and_returns_oldest`、
   `test_red_remove_one_of_duplicates_drops_oldest_only`）：
   `insert` 走到同键段末尾后，`_splice` 在每一层都因
   `pred.key == node.key` 而 `continue`，新节点一条边都不接。
   建议让第 0 层始终挂接到同键段尾部，高层前驱仍使用 `_preds`
   记录的 `< key` 节点（不可用段尾同键节点覆盖高层 update）。
3. **重复插入时 `_size` 加了两次**（
   `test_red_len_matches_scan_under_duplicate_inserts`）：
   `insert` 的同键分支内外各有一次 `self._size += 1`。
   建议删掉分支内那次，保留唯一的统一计数。
4. **remove 不摘除第 0 层链边，删除的键幽灵重现**（
   `test_red_remove_unlinks_node_from_level_zero`、
   `test_red_single_key_lifecycle`、
   `test_red_remove_keeps_other_keys_intact`）：
   前驱收集循环误写为 `while i > 0`，漏掉 backbone 层。
   建议改为 `while i >= 0`，第 0 层同样记录前驱并摘边。
5. **无副本时 remove 仍反复返回 True 并把计数扣成负数**（
   `test_red_remove_after_real_removal_returns_false`、
   `test_red_len_nonnegative_after_repeated_remove`）：
   为缺陷 4 的连带表现；修复第 0 层摘边后判定自然正确，
   另建议摘除后按需回缩 `_level`。
6. **`__contains__` 把 value 为 None 的现存键误判为不存在**（
   `test_red_contains_treats_none_value_as_missing`）：
   现写法为 `return self.find(key) is not None`，用 value 真值代替了
   键命中判据。建议沿链判定键是否存在，与 find 的取值返回分离。
7. **查找/插入退化为 O(n)，规模翻倍出现明显超线性拐点**（
   `test_red_no_superlinear_kink_from_10k_to_100k`）：
   缺陷 1 使跳表退化为单链表，1 万→2 万键点查均摊约翻倍、
   累计插入耗时约 4.5 倍（n² 特征）。修复缺陷 1、恢复几何层级
   分布后即回到 O(log n)。
8. **任意操作序列不变量被破坏**（
   `test_red_mixed_operation_streams_match_reference`）：
   固定 seed 混合插入/删除/查询/区间遍历流与朴素参考实现（插入序
   list + 稳定排序）逐步对拍，seed=0 在第 7 步（副本孤儿）即分叉，
   随后叠加幽灵删除与计数失真；是缺陷 2~5 的综合表现，
   修复上述根因后对拍全程一致。

README 未约定的自由行为未钉红用例，例如删除后 `max_height` 是否
回缩（仅要求其诊断“当前最大节点高度”，语义修复后可按需维护）。
