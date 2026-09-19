"""intervaltree 语义测试：逐条锁定 README《语义约定》。

运行方式（在仓库根目录下，两种均可，独立可重复）：
    python3 -m unittest tests.test_interval -v
    python3 tests/test_interval.py

允许存在红用例：源码与 README 不一致处用测试钉死，红用例上方的注释
写明「README 期望什么 / 实际发生什么」。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intervaltree import IntervalTree, OverlapError  # noqa: E402


class TestIntervalValidity(unittest.TestCase):
    """README 1：闭区间 [start, end]，start <= end，否则 ValueError。"""

    def test_rejects_start_greater_than_end(self):
        tree = IntervalTree()
        with self.assertRaises(ValueError):
            tree.insert(5, 4)

    def test_accepts_zero_length_interval(self):
        tree = IntervalTree()
        tree.insert(3, 3)
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree.point_query(3), [(3, 3)])


class TestOverlapAndInsert(unittest.TestCase):
    """README 2：闭区间端点相接算重叠；重复插入按重叠处理。"""

    def test_insert_disjoint_intervals_succeeds(self):
        tree = IntervalTree()
        tree.insert(1, 2)
        tree.insert(4, 4)  # 与 [1,2] 之间有空隙（点 3 不共享）
        self.assertEqual(len(tree), 2)

    def test_insert_overlapping_interval_raises_and_keeps_tree(self):
        tree = IntervalTree()
        tree.insert(1, 10)
        with self.assertRaises(OverlapError):
            tree.insert(5, 6)  # 被包含，显然重叠
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree.query_range(0, 100), [(1, 10)])

    def test_insert_duplicate_interval_raises(self):
        tree = IntervalTree()
        tree.insert(1, 3)
        with self.assertRaises(OverlapError):
            tree.insert(1, 3)
        self.assertEqual(len(tree), 1)

    # README 期望：闭区间端点相接也算重叠，[1,3] 之后插入 [3,5] 应抛
    # OverlapError（两区间共享点 3）。
    # 实际发生：源码 _has_overlap 用的是开区间判据 node.start < end 且
    # node.end > start，端点相接被放行，[3,5] 插入成功，len 变为 2。
    def test_insert_overlaps_when_endpoints_touch(self):
        tree = IntervalTree()
        tree.insert(1, 3)
        with self.assertRaises(OverlapError):
            tree.insert(3, 5)
        self.assertEqual(len(tree), 1)

    # README 期望：相同区间重复插入一律按重叠处理（点区间 [5,5] 也不例外）。
    # 实际发生：树按 (start, end) 二元组排序，相等元组被当作“更大”放进
    # 右子树，而开区间判据又判不出重叠，重复点区间被放进来，len 变为 2。
    def test_insert_duplicate_point_interval_raises(self):
        tree = IntervalTree()
        tree.insert(5, 5)
        with self.assertRaises(OverlapError):
            tree.insert(5, 5)
        self.assertEqual(len(tree), 1)


class TestRemove(unittest.TestCase):
    """README 3：删除完全相等的区间；不存在抛 KeyError 且树不变。"""

    def test_remove_existing_interval(self):
        tree = IntervalTree()
        tree.insert(2, 5)
        tree.insert(10, 20)
        tree.remove(2, 5)
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree.query_range(0, 100), [(10, 20)])

    def test_remove_then_reinsert_same_slot(self):
        tree = IntervalTree()
        tree.insert(2, 5)
        tree.remove(2, 5)
        tree.insert(2, 5)  # 删掉后同一窗口应能重新登记
        self.assertEqual(tree.query_range(0, 100), [(2, 5)])

    # README 期望：删除不存在的区间抛 KeyError，树保持不变（len 也不变）。
    # 实际发生：_delete 走到 None 静默返回 None，remove 不做存在性检查
    # 且无条件 self._size -= 1；不抛异常，len 还被错误地减 1。
    def test_remove_missing_raises_key_error(self):
        tree = IntervalTree()
        tree.insert(1, 2)
        with self.assertRaises(KeyError):
            tree.remove(9, 9)
        self.assertEqual(len(tree), 1)

    # README 期望：删除只影响目标区间，其余区间必须仍可查询（完整性第 6 条）。
    # 实际发生：被删节点左右子树皆有时，源码用后继节点覆盖本节点后直接执行
    # node.right = succ.right；当后继自身还有右子树时，原右链路上后继以外的
    # 区间（本例的 [20,22]）被整支丢弃，出现“登记着却查不到”。
    def test_remove_keeps_successor_right_subtree(self):
        tree = IntervalTree()
        for start, end in [(10, 12), (5, 7), (20, 22), (15, 17)]:
            tree.insert(start, end)
        tree.remove(10, 12)
        self.assertEqual(
            sorted(tree.query_range(0, 100)),
            [(5, 7), (15, 17), (20, 22)],
        )
        self.assertEqual(len(tree), 3)


class TestQueryRange(unittest.TestCase):
    """README 4：闭区间相交，s == hi 或 e == lo 都算，按 start 升序。"""

    def test_returns_intersecting_sorted_by_start(self):
        tree = IntervalTree()
        for start, end in [(30, 31), (5, 6), (20, 21), (10, 11)]:
            tree.insert(start, end)
        self.assertEqual(
            tree.query_range(8, 25),
            [(10, 11), (20, 21)],
        )

    def test_endpoint_equals_lo_counts(self):
        tree = IntervalTree()
        tree.insert(2, 5)
        self.assertEqual(tree.query_range(5, 9), [(2, 5)])  # e == lo

    def test_returns_empty_when_disjoint(self):
        tree = IntervalTree()
        tree.insert(10, 20)
        self.assertEqual(tree.query_range(21, 30), [])

    def test_rejects_lo_greater_than_hi(self):
        tree = IntervalTree()
        tree.insert(1, 2)
        with self.assertRaises(ValueError):
            tree.query_range(5, 4)

    # README 期望：[s,e] 与 [lo,hi] 共享任一点即相交，s == hi 算相交，
    # 故 query_range(0, 10) 必须包含 [10,20]。
    # 实际发生：_collect_range 收录判据写成 node.start < hi（开区间），
    # start 恰好等于 hi 的区间被漏掉，返回空列表。
    def test_start_equals_hi_counts(self):
        tree = IntervalTree()
        tree.insert(10, 20)
        self.assertEqual(tree.query_range(0, 10), [(10, 20)])


class TestPointQuery(unittest.TestCase):
    """README 5：返回覆盖点 x（s <= x <= e）的区间，按 start 升序。"""

    def test_endpoints_are_covered(self):
        tree = IntervalTree()
        tree.insert(2, 5)
        self.assertEqual(tree.point_query(2), [(2, 5)])
        self.assertEqual(tree.point_query(5), [(2, 5)])
        self.assertEqual(tree.point_query(6), [])

    def test_returns_covering_sorted_by_start(self):
        tree = IntervalTree()
        for start, end in [(30, 40), (5, 6), (10, 20)]:
            tree.insert(start, end)
        # [10,20] 与 [30,40] 不相交，可共存
        self.assertEqual(tree.point_query(15), [(10, 20)])
        self.assertEqual(tree.point_query(35), [(30, 40)])


class TestIntegrityAndLen(unittest.TestCase):
    """README 6/7：查询只取决于当前集合；len 与可查询区间数一致。"""

    def test_len_matches_queryable_count(self):
        tree = IntervalTree()
        for start, end in [(10, 20), (2, 4), (40, 50), (25, 30)]:
            tree.insert(start, end)
        tree.remove(2, 4)
        tree.remove(25, 30)
        self.assertEqual(len(tree), len(tree.query_range(0, 100)))
        self.assertEqual(tree.query_range(0, 100), [(10, 20), (40, 50)])

    # README 期望：同样三个区间的树，无论“插四个删一个”还是“直接插三个”，
    # 查询结果必须一致（结果只由当前集合决定）。
    # 实际发生：删除 [10,12] 走后继替换路径时丢了 [20,22]（与
    # test_remove_keeps_successor_right_subtree 同一根因），两棵树查询不一致。
    def test_query_results_independent_of_operation_history(self):
        tree_a = IntervalTree()
        for start, end in [(10, 12), (5, 7), (20, 22), (15, 17)]:
            tree_a.insert(start, end)
        tree_a.remove(10, 12)

        tree_b = IntervalTree()
        for start, end in [(5, 7), (15, 17), (20, 22)]:
            tree_b.insert(start, end)

        self.assertEqual(
            tree_a.query_range(0, 100),
            tree_b.query_range(0, 100),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
