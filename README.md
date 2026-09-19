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

测试文件：`tests/test_interval.py`（标准库 unittest）。
运行方式（仓库根目录，可独立重复运行）：

```bash
python3 -m unittest tests.test_interval -v
python3 tests/test_interval.py
```

共 20 个用例：15 绿 5 红。红用例及其对应缺陷、修复方向：

1. `TestInsertOverlap.test_endpoint_touching_insert_rejected`（红）
   - 缺陷：`_has_overlap` 用严格不等号 `node.start < end and node.end > start`
     判定重叠，端点相接（`start == 对方 end`）被误判为不重叠，本该报
     `OverlapError` 的插入被放行（违反语义 2）。
   - 修复方向：改为闭区间相交条件 `node.start <= end and node.end >= start`。
2. `TestInsertOverlap.test_duplicate_zero_length_interval_rejected`（红）
   - 缺陷：同一判定用严格不等号，相同退化点区间（如 `[4,4]` 重复插入）
     判为不重叠而被放行（违反语义 2）；与上一条同源。
   - 修复方向：同上，改为闭区间相交条件后重复点区间即按重叠拒绝。
3. `TestRemove.test_remove_missing_raises_keyerror_and_tree_unchanged`（红）
   - 缺陷：`_delete` 走到 `None` 时静默返回，`remove` 不抛 `KeyError`，且
     `_size -= 1` 无条件执行，删除不存在的区间会把计数减坏（违反语义 3、6、7）。
   - 修复方向：删除前先查找确认区间存在，不存在抛 `KeyError` 且不动 `_size`。
4. `TestRemove.test_remove_two_child_node_keeps_other_intervals`（红）
   - 缺陷：删除有两个孩子的节点时，用后继覆盖当前节点后直接令
     `node.right = succ.right`，后继节点本身未被摘除，后继区间丢失、树结构
     损坏、`len` 失真（违反语义 3、6、7，对应「删过几轮后查不到」的现象）。
   - 修复方向：覆盖后继值后先从右子树递归删除该后继，再 `_pull_up`。
5. `TestQueryRange.test_query_range_endpoint_hi_touch`（红）
   - 缺陷：`_collect_range` 用 `node.start < hi` 判定相交，`s == hi`
     （如 `[5,8]` 查 `[1,5]`）时漏收区间（违反语义 4；`e == lo` 的另一侧
     用 `node.end >= lo`，判定正确）。
   - 修复方向：改为 `node.start <= hi and node.end >= lo`。

其余 15 个用例（参数校验、内部重叠拒绝、重复区间拒绝、重叠插入后树不变、
正常删除与再插入、查询排序与过滤、`point_query` 端点覆盖等）全部为绿。
`python3 demo.py` 已验证照常跑通，本次未改动 `intervaltree/` 与 `demo.py`
任何一行。
