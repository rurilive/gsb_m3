# intervaltree

容量调度服务里的闭区间集合，登记和查询资源占用窗口用，纯标准库，
单线程使用。内部按 start 组织成增强二叉搜索树（子树维护 max_end 剪枝）。

## 语义约定（以下为本模块的正式行为定义）

1. **区间**：一律为闭区间 [start, end]，要求 start <= end，违反抛 `ValueError`。
2. **重叠**：两个闭区间共享至少一个点即算重叠，**端点相接也算重叠**
   （[1,3] 与 [3,5] 重叠于点 3，[1,3] 与 [3,4] 同理）。
   - `insert(start, end)`：与树中任一现有区间重叠时抛 `OverlapError`，
     树保持不变；否则插入。相同区间重复插入同样按重叠处理。
3. **remove(start, end)**：删除与参数完全相等的区间。**区间不存在时抛
   `KeyError`**，树保持不变。
4. **query_range(lo, hi)**：返回与 [lo, hi] 相交的所有区间，按 start 升序的
   `list[tuple]`。闭区间相交语义：区间 [s,e] 与 [lo,hi] 共享任一点即相交，
   **s == hi 或 e == lo 都算相交**。lo > hi 抛 `ValueError`。
5. **point_query(x)**：返回覆盖点 x（s <= x <= e）的所有区间，按 start 升序。
6. **完整性**：任意时刻的查询结果只由当前树中的区间集合决定，与历史插入、
   删除的操作序列无关。
7. **len(tree)**：返回当前区间个数，与可查询到的区间数一致。

## 运行

```bash
python3 demo.py
```


## 测试报告

运行方式（仓库根目录，独立可重复）：`python3 -m unittest tests.test_interval -v`
或 `python3 tests/test_interval.py`。共 20 个用例：**14 绿、6 红**。
红用例（`tests/test_interval.py` 内均有「README 期望 / 实际发生」注释）：

1. `test_insert_overlaps_when_endpoints_touch`（红）——缺陷：端点相接（[1,3] 与
   [3,5] 共享点 3）的插入被放行，违反 README 2「端点相接也算重叠」。修复方向：
   `_has_overlap` 的重叠判据由开区间的 `start < end and end > start` 改为闭区间的
   `start <= end and end >= start`。
2. `test_insert_duplicate_point_interval_raises`（红）——缺陷：重复插入点区间
   [5,5] 未按重叠拒绝，违反 README 2「相同区间重复插入按重叠处理」。修复方向：
   随第 1 条改闭区间判据，并把 `_insert` 的相等键处理为不再落入右子树（重叠检查
   本身会先拦住）。
3. `test_remove_missing_raises_key_error`（红）——缺陷：删除不存在的区间不抛
   `KeyError`，且 `len` 被错误减 1，违反 README 3、7。修复方向：`remove` 先判断
   区间是否存在，不存在抛 `KeyError`，存在才执行 `_delete` 并 `self._size -= 1`。
4. `test_remove_keeps_successor_right_subtree`（红）——缺陷：被删节点有左右两棵
   子树且后继节点自身带右子树时，`node.right = succ.right` 会把原右子树中后继以外
   的区间整支丢弃（“登记着却查不到”），违反 README 6、7。修复方向：后继复制后，
   改为递归删除原右子树中的后继节点（或让 `_delete` 返回节点并自底向上
   `_pull_up`），不要直接挂 `succ.right`。
5. `test_start_equals_hi_counts`（红）——缺陷：`query_range` 漏掉 `s == hi` 的区间
   （query_range(0,10) 查不到 [10,20]），违反 README 4 闭区间相交。修复方向：
   `_collect_range` 的收录判据由 `node.start < hi` 改为 `node.start <= hi`，并同步
   核对右子树下探条件。
6. `test_query_results_independent_of_operation_history`（红）——缺陷：相同当前集合
   经不同增删序列后查询结果不一致，是第 4 条删除丢区间的外显症状，违反 README 6；
   随第 4 条修复后转绿。

其余 14 个用例覆盖闭区间端点合法性、包含重叠拒绝且树不变、正常删除与删后重插、
`e == lo` 相交、不相交返回空、`lo > hi` 抛 `ValueError`、`point_query` 端点覆盖与
排序、`len` 与可查询数一致等，均通过；README 未约定的自由行为未加断言。
`python3 demo.py` 照常跑通，`intervaltree/` 源码与 `demo.py` 未做任何改动。
