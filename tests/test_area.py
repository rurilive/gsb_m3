"""基线测试：锁住改造前 areaunion.area.RectSet 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - 全部面积与周长能力都先把横纵坐标离散化，再对每个小格逐个判定；
  - union_area 对每个小格遇到第一个覆盖它的矩形就停；
  - area_at_least 与 area_exactly 对每个小格把全部矩形都数一遍；
  - perimeter 从覆盖布尔矩阵上数覆盖与未覆盖的分界；
  - independent_brute_area 等是三条各自独立的逐格慢速做法；
  - judge_count 报出最近一次逐格判定次数，node_access_count 恒为零。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from areaunion.area import (  # noqa: E402
    RectSet,
    Erro,
    RectErro,
    CountErro,
    IndexErro,
)


SAMPLE = [(0, 0, 2, 2), (1, 1, 3, 3), (10, 10, 11, 11), (10, 10, 10, 10)]


class TestConstruction(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(RectSet().count(), 0)

    def test_items_are_copied(self):
        s = RectSet(SAMPLE)
        s.rects.append((99, 99, 100, 100))
        self.assertEqual(s.count(), 4)

    def test_reversed_x(self):
        with self.assertRaises(RectErro):
            RectSet([(5, 0, 1, 2)])

    def test_reversed_y(self):
        with self.assertRaises(RectErro):
            RectSet([(0, 5, 2, 1)])

    def test_bad_arity(self):
        with self.assertRaises(RectErro):
            RectSet([(0, 0, 1)])

    def test_non_integer_endpoint(self):
        with self.assertRaises(RectErro):
            RectSet([(0, 0, 1, "a")])

    def test_bool_is_not_integer(self):
        with self.assertRaises(RectErro):
            RectSet([(True, 0, 1, 1)])

    def test_not_a_sequence(self):
        with self.assertRaises(RectErro):
            RectSet("abcd")

    def test_degenerate_point_is_ok(self):
        self.assertEqual(RectSet([(3, 3, 3, 3)]).count(), 1)

    def test_degenerate_line_is_ok(self):
        self.assertEqual(RectSet([(1, 2, 5, 2)]).count(), 1)


class TestCellCount(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(RectSet().cell_count(), 0)

    def test_single_point_rect(self):
        self.assertEqual(RectSet([(3, 3, 3, 3)]).cell_count(), 0)

    def test_single_line_rect(self):
        self.assertEqual(RectSet([(1, 2, 5, 2)]).cell_count(), 0)

    def test_single_box(self):
        self.assertEqual(RectSet([(0, 0, 2, 3)]).cell_count(), 1)

    def test_sample(self):
        # 横坐标 {0,1,2,3,10,11} 共 5 段，纵坐标 {0,1,2,3,10,11} 共 5 段。
        self.assertEqual(RectSet(SAMPLE).cell_count(), 25)


class TestUnionArea(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(RectSet().union_area(), 0)

    def test_single_box(self):
        self.assertEqual(RectSet([(0, 0, 2, 3)]).union_area(), 6)

    def test_point_rect_zero_area(self):
        self.assertEqual(RectSet([(3, 3, 3, 3)]).union_area(), 0)

    def test_line_rect_zero_area(self):
        self.assertEqual(RectSet([(1, 2, 5, 2)]).union_area(), 0)

    def test_duplicate_not_doubled(self):
        self.assertEqual(RectSet([(0, 0, 2, 2), (0, 0, 2, 2)]).union_area(), 4)

    def test_contained_swallowed(self):
        self.assertEqual(RectSet([(0, 0, 4, 4), (1, 1, 2, 2)]).union_area(), 16)

    def test_disjoint_add(self):
        self.assertEqual(
            RectSet([(0, 0, 2, 2), (10, 10, 12, 12)]).union_area(), 8
        )

    def test_touching_edge_not_double(self):
        # 两矩形共用边 x=2，并集面积不退化为重叠，仍是两块之和。
        self.assertEqual(
            RectSet([(0, 0, 2, 2), (2, 0, 4, 2)]).union_area(), 8
        )

    def test_negative_coords(self):
        self.assertEqual(RectSet([(-3, -3, -1, -1)]).union_area(), 4)

    def test_sample(self):
        self.assertEqual(RectSet(SAMPLE).union_area(), 8)


class TestAreaAtLeast(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(RectSet().area_at_least(1), 0)

    def test_single_box(self):
        self.assertEqual(RectSet([(0, 0, 2, 2)]).area_at_least(1), 4)

    def test_k_two_no_overlap(self):
        self.assertEqual(
            RectSet([(0, 0, 2, 2), (10, 10, 12, 12)]).area_at_least(2), 0
        )

    def test_k_two_overlap(self):
        self.assertEqual(
            RectSet([(0, 0, 2, 2), (1, 1, 3, 3)]).area_at_least(2), 1
        )

    def test_bad_k_zero(self):
        with self.assertRaises(CountErro):
            RectSet(SAMPLE).area_at_least(0)

    def test_bad_k_not_int(self):
        with self.assertRaises(CountErro):
            RectSet(SAMPLE).area_at_least("a")

    def test_sample(self):
        self.assertEqual(RectSet(SAMPLE).area_at_least(1), 8)
        self.assertEqual(RectSet(SAMPLE).area_at_least(2), 1)
        self.assertEqual(RectSet(SAMPLE).area_at_least(3), 0)


class TestAreaExactly(unittest.TestCase):
    def test_exactly_one_of_two_overlapping(self):
        s = RectSet([(0, 0, 2, 2), (1, 1, 3, 3)])
        self.assertEqual(s.area_exactly(1), 6)
        self.assertEqual(s.area_exactly(2), 1)

    def test_exactly_zero_counts_uncovered_cells(self):
        # 离散化只在有限坐标范围内取格，未覆盖的小格计入恰好零次面积。
        s = RectSet([(0, 0, 2, 2), (3, 3, 5, 5)])
        self.assertEqual(s.area_exactly(0), 17)

    def test_negative_k_rejected(self):
        with self.assertRaises(CountErro):
            RectSet(SAMPLE).area_exactly(-1)

    def test_sample(self):
        self.assertEqual(RectSet(SAMPLE).area_exactly(1), 7)
        self.assertEqual(RectSet(SAMPLE).area_exactly(2), 1)


class TestMaxOverlap(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(RectSet().max_overlap(), 0)

    def test_single(self):
        self.assertEqual(RectSet([(0, 0, 2, 2)]).max_overlap(), 1)

    def test_triple_duplicate(self):
        s = RectSet([(0, 0, 2, 2), (0, 0, 2, 2), (0, 0, 2, 2)])
        self.assertEqual(s.max_overlap(), 3)

    def test_sample(self):
        self.assertEqual(RectSet(SAMPLE).max_overlap(), 2)


class TestPerimeter(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(RectSet().perimeter(), 0)

    def test_single_box(self):
        self.assertEqual(RectSet([(0, 0, 2, 3)]).perimeter(), 10)

    def test_duplicate_not_doubled(self):
        self.assertEqual(
            RectSet([(0, 0, 2, 2), (0, 0, 2, 2)]).perimeter(), 8
        )

    def test_contained_swallowed(self):
        self.assertEqual(RectSet([(0, 0, 4, 4), (1, 1, 2, 2)]).perimeter(), 16)

    def test_touching_share_edge_merges(self):
        # 两矩形共边拼成 4x2 大矩形，周长是并集外轮廓。
        self.assertEqual(
            RectSet([(0, 0, 2, 2), (2, 0, 4, 2)]).perimeter(), 12
        )

    def test_disjoint_add(self):
        self.assertEqual(
            RectSet([(0, 0, 2, 2), (10, 10, 12, 12)]).perimeter(), 16
        )

    def test_point_and_line_have_no_perimeter(self):
        self.assertEqual(RectSet([(3, 3, 3, 3)]).perimeter(), 0)
        self.assertEqual(RectSet([(1, 2, 5, 2)]).perimeter(), 0)

    def test_negative_coords(self):
        self.assertEqual(RectSet([(-3, -3, -1, -1)]).perimeter(), 8)

    def test_sample(self):
        self.assertEqual(RectSet(SAMPLE).perimeter(), 16)


class TestPointQueries(unittest.TestCase):
    def test_covers_point_on_corner(self):
        self.assertEqual(RectSet(SAMPLE).covers_point(0, 0), [0])

    def test_covers_point_shared(self):
        self.assertEqual(RectSet(SAMPLE).covers_point(1, 1), [0, 1])

    def test_covers_point_none(self):
        self.assertEqual(RectSet(SAMPLE).covers_point(5, 5), [])

    def test_coverage_count_at(self):
        self.assertEqual(RectSet(SAMPLE).coverage_count_at(1, 1), 2)

    def test_is_covered(self):
        s = RectSet(SAMPLE)
        self.assertTrue(s.is_covered(0, 0))
        self.assertTrue(s.is_covered(11, 11))
        self.assertFalse(s.is_covered(5, 5))

    def test_bad_point(self):
        with self.assertRaises(RectErro):
            RectSet(SAMPLE).covers_point("a", 0)


class TestSolveAll(unittest.TestCase):
    def test_bundle(self):
        got = RectSet(SAMPLE).solve_all(2)
        self.assertEqual(got["union_area"], 8)
        self.assertEqual(got["perimeter"], 16)
        self.assertEqual(got["area_at_least"], 1)
        self.assertEqual(got["area_exactly"], 1)


class TestIndependentPaths(unittest.TestCase):
    def test_area_matches(self):
        cases = [
            SAMPLE,
            [],
            [(0, 0, 2, 3)],
            [(3, 3, 3, 3)],
            [(1, 2, 5, 2)],
            [(0, 0, 4, 4), (1, 1, 2, 2)],
            [(-3, -3, -1, -1), (-2, -2, 2, 2)],
            [(0, 0, 2, 2), (2, 0, 4, 2)],
        ]
        for case in cases:
            s = RectSet(case)
            self.assertEqual(s.independent_brute_area(), s.union_area(), repr(case))

    def test_area_at_least_matches(self):
        cases = [SAMPLE, [(0, 0, 2, 2), (1, 1, 3, 3)], [(0, 0, 2, 2), (10, 10, 12, 12)]]
        for case in cases:
            for k in (1, 2, 3):
                s = RectSet(case)
                self.assertEqual(
                    s.independent_brute_area_at_least(k),
                    s.area_at_least(k),
                    repr(case) + " k=" + str(k),
                )

    def test_perimeter_matches(self):
        cases = [
            SAMPLE,
            [],
            [(0, 0, 2, 3)],
            [(3, 3, 3, 3)],
            [(1, 2, 5, 2)],
            [(0, 0, 4, 4), (1, 1, 2, 2)],
            [(0, 0, 2, 2), (2, 0, 4, 2)],
            [(-3, -3, -1, -1), (-2, -2, 2, 2)],
        ]
        for case in cases:
            s = RectSet(case)
            self.assertEqual(
                s.independent_brute_perimeter(), s.perimeter(), repr(case)
            )

    def test_at_least_sums_to_exactly_partition(self):
        # 至少 1 次面积 = 恰好 1 次 + 恰好 2 次 + ... 在有限离散范围内成立。
        s = RectSet([(0, 0, 2, 2), (1, 1, 3, 3), (2, 2, 4, 4)])
        top = s.max_overlap()
        total = 0
        for k in range(1, top + 1):
            total += s.area_exactly(k)
        self.assertEqual(total, s.union_area())


class TestScaleMetrics(unittest.TestCase):
    def test_judge_count_zero_when_empty(self):
        s = RectSet()
        s.union_area()
        self.assertEqual(s.judge_count(), 0)

    def test_judge_count_positive(self):
        s = RectSet([(0, 0, 2, 2)])
        s.union_area()
        self.assertEqual(s.judge_count(), 1)

    def test_node_access_zero(self):
        s = RectSet(SAMPLE)
        s.union_area()
        self.assertEqual(s.node_access_count(), 0)

    def test_node_access_zero_after_count_grid(self):
        s = RectSet(SAMPLE)
        s.max_overlap()
        self.assertEqual(s.node_access_count(), 0)

    def test_judge_count_is_pure(self):
        s = RectSet(SAMPLE)
        s.union_area()
        first = s.judge_count()
        s.union_area()
        self.assertEqual(s.judge_count(), first)


class TestDeterminism(unittest.TestCase):
    def test_repeated_union_area(self):
        a = RectSet(SAMPLE).union_area()
        b = RectSet(SAMPLE).union_area()
        self.assertEqual(a, b)

    def test_two_paths_agree_repeatedly(self):
        s = RectSet(SAMPLE)
        self.assertEqual(s.independent_brute_area(), s.independent_brute_area())
        self.assertEqual(s.union_area(), s.union_area())
        self.assertEqual(s.perimeter(), s.perimeter())

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(RectErro, Erro))
        self.assertTrue(issubclass(CountErro, Erro))
        self.assertTrue(issubclass(IndexErro, Erro))
        self.assertTrue(issubclass(Erro, Exception))


if __name__ == "__main__":
    unittest.main()
