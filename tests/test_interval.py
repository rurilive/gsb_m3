"""intervaltree 语义锁定测试。

以 intervaltree/README.md 的「语义约定」为准，逐条锁定。
纯标准库 unittest，可从仓库根目录独立重复运行：

    python3 -m unittest tests.test_interval -v
    python3 tests/test_interval.py

红用例（当前源码与 README 有出入）上方以注释标明：
README 期望什么 / 实际发生什么。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intervaltree import IntervalTree, OverlapError


class TestIntervalValidation(unittest.TestCase):
    """语义 1：闭区间 [start, end]，start <= end，违反抛 ValueError。"""

    def test_insert_rejects_start_greater_than_end(self):
        tree = IntervalTree()
        with self.assertRaises(ValueError):
            tree.insert(5, 4)

    def test_insert_accepts_zero_length_interval(self):
        tree = IntervalTree()
        tree.insert(7, 7)
        self.assertEqual(tree.point_query(7), [(7, 7)])

    def test_query_range_rejects_lo_greater_than_hi(self):
        tree = IntervalTree()
        with self.assertRaises(ValueError):
            tree.query_range(3, 2)


class TestInsertOverlap(unittest.TestCase):
    """语义 2：闭区间共享任一点即重叠，端点相接也算重叠。"""

    def test_interior_overlap_rejected(self):
        tree = IntervalTree()
        tree.insert(1, 5)
        with self.assertRaises(OverlapError):
            tree.insert(2, 3)

    def test_duplicate_interval_rejected(self):
        tree = IntervalTree()
        tree.insert(2, 8)
        with self.assertRaises(OverlapError):
            tree.insert(2, 8)

    def test_overlapping_insert_leaves_tree_unchanged(self):
        tree = IntervalTree()
        tree.insert(1, 5)
        with self.assertRaises(OverlapError):
            tree.insert(4, 6)
        self.assertEqual(tree.query_range(0, 100), [(1, 5)])
        self.assertEqual(len(tree), 1)

    def test_disjoint_intervals_inserted(self):
        tree = IntervalTree()
        tree.insert(1, 3)
        tree.insert(5, 8)
        self.assertEqual(tree.query_range(0, 100), [(1, 3), (5, 8)])

    # 红用例：
    # README 期望：端点相接也算重叠（[1,3] 与 [3,5]、[1,3] 与 [3,4]），
    #             insert 应抛 OverlapError。
    # 实际发生：_has_overlap 用严格不等号 node.start < end 判定，
    #           共享端点（start == 对方 end）时判为不重叠，插入被放行。
    def test_endpoint_touching_insert_rejected(self):
        tree = IntervalTree()
        tree.insert(1, 3)
        with self.assertRaises(OverlapError):
            tree.insert(3, 5)

        tree = IntervalTree()
        tree.insert(3, 4)
        with self.assertRaises(OverlapError):
            tree.insert(1, 3)

    # 红用例：
    # README 期望：相同区间（含退化点区间 [4,4]）重复插入按重叠处理，
    #             应抛 OverlapError。
    # 实际发生：node.start < end and node.end > start 在退化为同一点时
    #           为 4 < 4 / 4 > 4，判定不重叠，重复点区间被放行（len 变 2）。
    def test_duplicate_zero_length_interval_rejected(self):
        tree = IntervalTree()
        tree.insert(4, 4)
        with self.assertRaises(OverlapError):
            tree.insert(4, 4)


class TestRemove(unittest.TestCase):
    """语义 3：remove 删除完全相等的区间；不存在时抛 KeyError，树不变。"""

    def test_remove_existing_interval(self):
        tree = IntervalTree()
        tree.insert(1, 3)
        tree.insert(5, 8)
        tree.remove(1, 3)
        self.assertEqual(tree.query_range(0, 100), [(5, 8)])
        self.assertEqual(len(tree), 1)

    def test_remove_then_reinsert_same_interval(self):
        tree = IntervalTree()
        tree.insert(1, 3)
        tree.remove(1, 3)
        tree.insert(1, 3)
        self.assertEqual(tree.query_range(0, 100), [(1, 3)])

    # 红用例：
    # README 期望：区间不存在时 remove 抛 KeyError，树保持不变
    #             （语义 3 + 语义 6 + 语义 7）。
    # 实际发生：_delete 对 None 静默返回，remove 不抛任何异常，
    #           且无条件 _size -= 1，计数被破坏（变成 -1）。
    def test_remove_missing_raises_keyerror_and_tree_unchanged(self):
        tree = IntervalTree()
        tree.insert(1, 2)
        with self.assertRaises(KeyError):
            tree.remove(9, 9)
        self.assertEqual(tree.query_range(0, 100), [(1, 2)])
        self.assertEqual(len(tree), 1)

    # 红用例：
    # README 期望：删除只影响被删区间本身，其余区间仍可查询（语义 3、6、7）。
    # 实际发生：删除有两个孩子的节点时，_delete 用后继节点覆盖当前节点后
    #           直接把 node.right 设为 succ.right，后继本身（以及后继若有的
    #           右子树）没有被摘除，导致后继区间丢失、树结构损坏、len 失真。
    def test_remove_two_child_node_keeps_other_intervals(self):
        tree = IntervalTree()
        for start, end in [(10, 10), (5, 5), (15, 15), (12, 12)]:
            tree.insert(start, end)
        tree.remove(10, 10)
        self.assertEqual(tree.query_range(0, 100), [(5, 5), (12, 12), (15, 15)])
        self.assertEqual(len(tree), 3)


class TestQueryRange(unittest.TestCase):
    """语义 4：query_range 返回与闭区间 [lo,hi] 相交的区间，按 start 升序。"""

    def test_query_range_returns_intervals_sorted_by_start(self):
        tree = IntervalTree()
        for start, end in [(40, 50), (2, 5), (25, 30), (10, 20)]:
            tree.insert(start, end)
        self.assertEqual(
            tree.query_range(0, 100),
            [(2, 5), (10, 20), (25, 30), (40, 50)],
        )

    def test_query_range_filters_non_intersecting(self):
        tree = IntervalTree()
        tree.insert(1, 3)
        tree.insert(8, 10)
        self.assertEqual(tree.query_range(4, 7), [])

    def test_query_range_endpoint_lo_touch(self):
        tree = IntervalTree()
        tree.insert(1, 5)
        self.assertEqual(tree.query_range(5, 8), [(1, 5)])

    # 红用例：
    # README 期望：s == hi 算相交，[5,8] 与查询 [1,5] 共享端点 5，应返回 [(5,8)]。
    # 实际发生：_collect_range 用 node.start < hi 判定，hi 等于区间 start 时
    #           漏收，返回 []。
    def test_query_range_endpoint_hi_touch(self):
        tree = IntervalTree()
        tree.insert(5, 8)
        self.assertEqual(tree.query_range(1, 5), [(5, 8)])


class TestPointQuery(unittest.TestCase):
    """语义 5：point_query 返回覆盖点 x（s <= x <= e）的区间，按 start 升序。"""

    def test_point_query_endpoints_covered(self):
        tree = IntervalTree()
        tree.insert(2, 5)
        self.assertEqual(tree.point_query(2), [(2, 5)])
        self.assertEqual(tree.point_query(5), [(2, 5)])

    def test_point_query_zero_length_interval(self):
        tree = IntervalTree()
        tree.insert(3, 3)
        self.assertEqual(tree.point_query(3), [(3, 3)])
        self.assertEqual(tree.point_query(2), [])
        self.assertEqual(tree.point_query(4), [])

    def test_point_query_filters_disjoint_intervals(self):
        tree = IntervalTree()
        for start, end in [(1, 3), (5, 7), (9, 10)]:
            tree.insert(start, end)
        self.assertEqual(tree.point_query(6), [(5, 7)])
        self.assertEqual(tree.point_query(4), [])
        self.assertEqual(tree.point_query(8), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
