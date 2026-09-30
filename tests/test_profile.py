"""基线测试：锁住改造前 profiledp.profile.ProfileDp 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - brute_placements 递归试探每个最靠前的空格，逐个尝试全部放置；
  - brute_count 就是全部铺满方案的个数，普通骨牌与 L 形都按个数计；
  - brute_judge 逐格检查是否落在网格内且恰好覆盖一次；
  - brute_best 枚举全部铺满方案逐个累计权重取最优；
  - independent_brute 与 independent_rows 是两条独立慢速做法，与主路径对账。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from profiledp.profile import (  # noqa: E402
    ProfileDp,
    Erro,
    SizeErro,
    GridErro,
    WeightErro,
    ShapeErro,
    MAX_MASK_BITS,
)

DOMINO = ("domino_h", "domino_v")
ALL_SHAPES = ("domino_h", "domino_v", "L_a", "L_b")


class TestConstruction(unittest.TestCase):
    def test_dimensions(self):
        p = ProfileDp(3, 4)
        self.assertEqual((p.rows, p.cols), (3, 4))

    def test_default_shapes(self):
        self.assertEqual(ProfileDp(2, 2).shape_names, ["domino_h", "domino_v"])

    def test_negative_rows(self):
        with self.assertRaises(SizeErro):
            ProfileDp(-1, 2)

    def test_negative_cols(self):
        with self.assertRaises(SizeErro):
            ProfileDp(2, -1)

    def test_bool_is_not_int(self):
        with self.assertRaises(SizeErro):
            ProfileDp(2, True)

    def test_width_over_mask_bits(self):
        with self.assertRaises(SizeErro):
            ProfileDp(2, MAX_MASK_BITS + 1)

    def test_width_at_mask_bits_is_ok(self):
        self.assertEqual(ProfileDp(1, MAX_MASK_BITS).cols, MAX_MASK_BITS)

    def test_bad_shape_name(self):
        with self.assertRaises(ShapeErro):
            ProfileDp(2, 2, names=("bogus",))

    def test_empty_shape_names(self):
        with self.assertRaises(ShapeErro):
            ProfileDp(2, 2, names=())

    def test_obstacle_out_of_range(self):
        with self.assertRaises(GridErro):
            ProfileDp(2, 2, obstacles=[(5, 5)])

    def test_bad_obstacle_tuple(self):
        with self.assertRaises(GridErro):
            ProfileDp(2, 2, obstacles=[(0,)])


class TestDominoCounts(unittest.TestCase):
    def test_empty_grid(self):
        self.assertEqual(ProfileDp(0, 0).brute_count(), 1)

    def test_zero_column_grid(self):
        self.assertEqual(ProfileDp(0, 3).brute_count(), 1)

    def test_single_cell(self):
        self.assertEqual(ProfileDp(1, 1).brute_count(), 0)

    def test_single_row_pair(self):
        self.assertEqual(ProfileDp(1, 2).brute_count(), 1)

    def test_single_row_odd(self):
        self.assertEqual(ProfileDp(1, 3).brute_count(), 0)

    def test_two_by_two(self):
        self.assertEqual(ProfileDp(2, 2).brute_count(), 2)

    def test_two_by_three(self):
        self.assertEqual(ProfileDp(2, 3).brute_count(), 3)

    def test_two_by_four(self):
        self.assertEqual(ProfileDp(2, 4).brute_count(), 5)

    def test_three_by_two(self):
        self.assertEqual(ProfileDp(3, 2).brute_count(), 3)

    def test_three_by_three(self):
        self.assertEqual(ProfileDp(3, 3).brute_count(), 0)

    def test_three_by_four(self):
        self.assertEqual(ProfileDp(3, 4).brute_count(), 11)

    def test_four_by_four(self):
        self.assertEqual(ProfileDp(4, 4).brute_count(), 36)

    def test_one_by_five(self):
        self.assertEqual(ProfileDp(1, 5).brute_count(), 0)


class TestAllShapeCounts(unittest.TestCase):
    def test_two_by_two(self):
        self.assertEqual(ProfileDp(2, 2, names=ALL_SHAPES).brute_count(), 2)

    def test_two_by_four(self):
        self.assertEqual(ProfileDp(2, 4, names=ALL_SHAPES).brute_count(), 6)

    def test_three_by_three(self):
        self.assertEqual(ProfileDp(3, 3, names=ALL_SHAPES).brute_count(), 4)

    def test_three_by_four(self):
        self.assertEqual(ProfileDp(3, 4, names=ALL_SHAPES).brute_count(), 18)

    def test_four_by_four(self):
        self.assertEqual(ProfileDp(4, 4, names=ALL_SHAPES).brute_count(), 83)

    def test_single_row_needs_three_cells_but_L_cannot_fit(self):
        # 一行三格面积是三、恰好是一块 L 的面积，但 L 跨两行，放不下。
        self.assertEqual(ProfileDp(1, 3, names=ALL_SHAPES).brute_count(), 0)

    def test_two_by_two_triple_shape_not_fitting(self):
        # 两格一寸的面积是四，凑不出三的整数倍。
        self.assertEqual(ProfileDp(2, 2, names=("L_a",)).brute_count(), 0)


class TestCanonical(unittest.TestCase):
    def test_empty_canonical(self):
        self.assertEqual(ProfileDp(0, 0).brute_canonical(), [])

    def test_no_solution_is_none(self):
        self.assertIsNone(ProfileDp(1, 1).brute_canonical())

    def test_two_by_two_canonical(self):
        self.assertEqual(
            ProfileDp(2, 2).brute_canonical(),
            ["domino_hdomino_h", "domino_hdomino_h"],
        )

    def test_one_by_three_obstacle(self):
        p = ProfileDp(1, 3, obstacles=[(0, 0)])
        self.assertEqual(p.brute_canonical(), [".domino_hdomino_h"])


class TestObstacles(unittest.TestCase):
    def test_two_by_two_corner_blocks_all(self):
        p = ProfileDp(2, 2, names=ALL_SHAPES, obstacles=[(0, 0)])
        self.assertEqual(p.brute_count(), 0)

    def test_two_by_two_one_obstacle_leaves_single_L(self):
        p = ProfileDp(2, 2, names=ALL_SHAPES, obstacles=[(1, 1)])
        self.assertEqual(p.brute_count(), 1)

    def test_domino_two_by_two_obstacle_blocks(self):
        p = ProfileDp(2, 2, names=DOMINO, obstacles=[(1, 1)])
        self.assertEqual(p.brute_count(), 0)

    def test_three_by_four_two_obstacles(self):
        p = ProfileDp(3, 4, names=ALL_SHAPES, obstacles=[(0, 0), (2, 3)])
        self.assertEqual(p.brute_count(), 6)

    def test_three_by_four_domino_two_obstacles(self):
        p = ProfileDp(3, 4, names=DOMINO, obstacles=[(0, 0), (2, 3)])
        self.assertEqual(p.brute_count(), 5)

    def test_three_by_three_diagonal_obstacles(self):
        p = ProfileDp(3, 3, names=ALL_SHAPES, obstacles=[(0, 0), (2, 2)])
        self.assertEqual(p.brute_count(), 3)

    def test_high_obstacle_ratio_no_solution(self):
        full = [(r, c) for r in range(2) for c in range(3)]
        keep = [(0, 0)]
        blocks = [cell for cell in full if cell not in keep]
        p = ProfileDp(2, 3, obstacles=blocks)
        self.assertEqual(p.brute_count(), 0)


class TestJudge(unittest.TestCase):
    def test_valid_layout(self):
        p = ProfileDp(2, 2)
        self.assertTrue(p.brute_judge([["domino_h", 0, 0], ["domino_h", 1, 0]]))

    def test_overlap_is_invalid(self):
        p = ProfileDp(2, 2)
        self.assertFalse(p.brute_judge([["domino_h", 0, 0], ["domino_h", 0, 1]]))

    def test_out_of_range_is_invalid(self):
        p = ProfileDp(2, 2)
        self.assertFalse(p.brute_judge([["domino_h", 0, 1]]))

    def test_incomplete_is_invalid(self):
        p = ProfileDp(2, 2)
        self.assertFalse(p.brute_judge([["domino_h", 0, 0]]))

    def test_obstacle_coverage_is_invalid(self):
        p = ProfileDp(2, 2, obstacles=[(0, 0)])
        self.assertFalse(p.brute_judge([["domino_h", 0, 0]]))

    def test_obstacle_left_free_layout_is_valid(self):
        p = ProfileDp(2, 2, names=ALL_SHAPES, obstacles=[(1, 1)])
        self.assertTrue(p.brute_judge([["L_a", 0, 0]]))

    def test_empty_layout_on_empty_grid_is_valid(self):
        self.assertTrue(ProfileDp(0, 0).brute_judge([]))


class TestBest(unittest.TestCase):
    def test_single_L_under_obstacle(self):
        p = ProfileDp(2, 2, names=ALL_SHAPES, obstacles=[(1, 1)])
        value, layout = p.brute_best([[5, 1], [1, 0]])
        self.assertEqual(value, 7)
        self.assertEqual(layout, [("L_a", 0, 0)])

    def test_domino_tie_takes_canonical(self):
        p = ProfileDp(2, 3, names=DOMINO)
        value, _ = p.brute_best([[3, 3, 3], [1, 1, 1]])
        self.assertEqual(value, 12)

    def test_zero_weight(self):
        p = ProfileDp(3, 4, names=DOMINO)
        value, layout = p.brute_best([[0] * 4 for _ in range(3)])
        self.assertEqual(value, 0)
        self.assertEqual(len(layout), 6)

    def test_negative_weight(self):
        p = ProfileDp(2, 2, names=DOMINO)
        value, _ = p.brute_best([[-5, -5], [-5, -5]])
        self.assertEqual(value, -20)

    def test_no_solution_returns_none(self):
        p = ProfileDp(1, 1, names=DOMINO)
        self.assertEqual(p.brute_best([[0]]), (None, None))

    def test_bad_weight_shape(self):
        p = ProfileDp(2, 2, names=DOMINO)
        with self.assertRaises(WeightErro):
            p.brute_best([[0, 0]])

    def test_nonnumeric_weight(self):
        p = ProfileDp(2, 2, names=DOMINO)
        with self.assertRaises(WeightErro):
            p.brute_best([[0, "a"], [0, 0]])


class TestIndependentPaths(unittest.TestCase):
    def test_brute_path_matches(self):
        p = ProfileDp(3, 4, names=ALL_SHAPES)
        count, canon = p.independent_brute()
        self.assertEqual(count, p.brute_count())
        self.assertEqual(canon, p.brute_canonical())

    def test_row_path_matches_domino(self):
        for rows in range(0, 5):
            for cols in range(0, 5):
                p = ProfileDp(rows, cols, names=DOMINO)
                self.assertEqual(
                    p.independent_rows(),
                    p.brute_count(),
                    "domino %dx%d" % (rows, cols),
                )

    def test_row_path_matches_all_shapes(self):
        for rows in range(0, 4):
            for cols in range(0, 5):
                p = ProfileDp(rows, cols, names=ALL_SHAPES)
                self.assertEqual(
                    p.independent_rows(),
                    p.brute_count(),
                    "all shapes %dx%d" % (rows, cols),
                )

    def test_row_path_matches_with_obstacles(self):
        cases = [
            ([(0, 0)], (2, 2)),
            ([(1, 1)], (2, 2)),
            ([(1, 1)], (3, 3)),
            ([(0, 0), (2, 3)], (3, 4)),
            ([(0, 0), (2, 2)], (3, 3)),
            ([(0, 0)], (1, 3)),
        ]
        for obstacles, (rows, cols) in cases:
            p = ProfileDp(rows, cols, names=ALL_SHAPES, obstacles=obstacles)
            self.assertEqual(
                p.independent_rows(),
                p.brute_count(),
                "%dx%d %r" % (rows, cols, obstacles),
            )


class TestScaleMetrics(unittest.TestCase):
    def test_brute_visit_count_positive(self):
        p = ProfileDp(3, 4, names=DOMINO)
        p.brute_count()
        self.assertGreater(p.brute_visit_count, 0)

    def test_outline_visit_count_zero_baseline(self):
        p = ProfileDp(3, 4, names=DOMINO)
        p.brute_count()
        self.assertEqual(p.outline_visit_count, 0)

    def test_row_visit_count_positive(self):
        p = ProfileDp(3, 4, names=DOMINO)
        p.independent_rows()
        self.assertGreater(p.row_visit_count, 0)

    def test_fresh_instance_counts_zero(self):
        p = ProfileDp(3, 4, names=DOMINO)
        self.assertEqual(p.brute_visit_count, 0)
        self.assertEqual(p.row_visit_count, 0)
        self.assertEqual(p.outline_visit_count, 0)
        self.assertEqual(p.judge_visits, 0)


class TestDeterminism(unittest.TestCase):
    def test_repeated_calls_agree(self):
        a = ProfileDp(3, 4, names=ALL_SHAPES).brute_placements()
        b = ProfileDp(3, 4, names=ALL_SHAPES).brute_placements()
        self.assertEqual(a, b)

    def test_counts_reset_between_calls(self):
        p = ProfileDp(3, 4, names=DOMINO)
        p.brute_count()
        first = p.brute_visit_count
        p.brute_count()
        self.assertEqual(p.brute_visit_count, first)

    def test_two_paths_agree_repeatedly(self):
        p = ProfileDp(3, 4, names=ALL_SHAPES)
        self.assertEqual(p.independent_rows(), p.independent_rows())

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(SizeErro, Erro))
        self.assertTrue(issubclass(GridErro, Erro))
        self.assertTrue(issubclass(WeightErro, Erro))
        self.assertTrue(issubclass(ShapeErro, Erro))
        self.assertTrue(issubclass(Erro, Exception))


if __name__ == "__main__":
    unittest.main()
