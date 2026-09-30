"""基线测试：锁住改造前 bitmaskx.bitmask.MaskDp 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - shortest_hamiltonian 与 shortest_cycle 对起点之外的全部点枚举全排列，
    逐个累计代价取最小；
  - min_cover 按个数从小到大枚举全部子集组合，逐个判定并集是否盖住目标；
  - min_groups 递归枚举全部集合划分，逐个校验每组内部两两相容取组数最小。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bitmaskx.bitmask import (  # noqa: E402
    MaskDp,
    Erro,
    SizeErro,
    GraphErro,
    WeightErro,
    CoverErro,
)


DIST4 = [
    [0, 3, 7, 5],
    [3, 0, 2, 6],
    [7, 2, 0, 4],
    [5, 6, 4, 0],
]


class TestBasics(unittest.TestCase):
    def test_full_mask(self):
        self.assertEqual(MaskDp(0).full_mask(), 0)
        self.assertEqual(MaskDp(4).full_mask(), 0b1111)

    def test_mask_of_and_elements_of(self):
        k = MaskDp(5)
        self.assertEqual(k.mask_of([0, 2, 4]), 0b10101)
        self.assertEqual(k.elements_of(0b10101), [0, 2, 4])

    def test_elements_of_empty(self):
        self.assertEqual(MaskDp(3).elements_of(0), [])

    def test_mask_of_out_of_range(self):
        with self.assertRaises(SizeErro):
            MaskDp(3).mask_of([0, 5])

    def test_mask_of_duplicate(self):
        with self.assertRaises(SizeErro):
            MaskDp(3).mask_of([1, 1])

    def test_negative_size(self):
        with self.assertRaises(SizeErro):
            MaskDp(-1)

    def test_bool_size_is_not_int(self):
        with self.assertRaises(SizeErro):
            MaskDp(True)


class TestHamiltonianBaseline(unittest.TestCase):
    def setUp(self):
        self.k = MaskDp(4)

    def test_zero_point_raises(self):
        with self.assertRaises(GraphErro):
            MaskDp(0).shortest_hamiltonian([], 0)

    def test_one_point_is_zero(self):
        cost, path = MaskDp(1).shortest_hamiltonian([[0]], 0)
        self.assertEqual(cost, 0)
        self.assertEqual(path, [0])

    def test_three_points(self):
        dist = [[0, 1, 5], [1, 0, 2], [5, 2, 0]]
        cost, path = self.k.__class__(3).shortest_hamiltonian(dist, 0)
        self.assertEqual(cost, 3)
        self.assertEqual(path, [0, 1, 2])

    def test_four_points(self):
        cost, path = self.k.shortest_hamiltonian(DIST4, 0)
        self.assertEqual(cost, 9)
        self.assertEqual(path, [0, 1, 2, 3])

    def test_start_other_than_zero(self):
        cost, path = self.k.shortest_hamiltonian(DIST4, 2)
        self.assertEqual(cost, 10)
        self.assertEqual(path, [2, 1, 0, 3])

    def test_tie_takes_lexicographically_smallest(self):
        dist = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        cost, path = MaskDp(3).shortest_hamiltonian(dist, 0)
        self.assertEqual(cost, 0)
        self.assertEqual(path, [0, 1, 2])

    def test_negative_weights_allowed(self):
        dist = [[0, -5, 4], [-5, 0, -3], [4, -3, 0]]
        cost, path = MaskDp(3).shortest_hamiltonian(dist, 0)
        self.assertEqual(cost, -8)
        self.assertEqual(path, [0, 1, 2])

    def test_perm_visits_positive(self):
        self.k.shortest_hamiltonian(DIST4, 0)
        self.assertGreater(self.k.perm_visits, 0)

    def test_bad_shape_raises(self):
        with self.assertRaises(GraphErro):
            self.k.shortest_hamiltonian([[0, 1], [1, 0]], 0)

    def test_nonnumeric_weight_raises(self):
        dist = [[0, "a"], ["a", 0]]
        with self.assertRaises(WeightErro):
            MaskDp(2).shortest_hamiltonian(dist, 0)

    def test_start_out_of_range_raises(self):
        with self.assertRaises(GraphErro):
            self.k.shortest_hamiltonian(DIST4, 9)


class TestHamiltonianBacktrackBaseline(unittest.TestCase):
    def test_matches_permutation_path(self):
        k = MaskDp(4)
        a = k.shortest_hamiltonian(DIST4, 0)
        k = MaskDp(4)
        b = k.shortest_hamiltonian_backtrack(DIST4, 0)
        self.assertEqual(a, b)

    def test_backtrack_visits_positive(self):
        k = MaskDp(4)
        k.shortest_hamiltonian_backtrack(DIST4, 0)
        self.assertGreater(k.backtrack_visits, 0)

    def test_single_point(self):
        cost, path = MaskDp(1).shortest_hamiltonian_backtrack([[0]], 0)
        self.assertEqual((cost, path), (0, [0]))


class TestCycleBaseline(unittest.TestCase):
    def setUp(self):
        self.k = MaskDp(4)

    def test_cycle_two_points(self):
        dist = [[0, 7], [7, 0]]
        cost, path = MaskDp(2).shortest_cycle(dist, 0)
        self.assertEqual(cost, 14)
        self.assertEqual(path, [0, 1, 0])

    def test_cycle_four_points(self):
        cost, path = self.k.shortest_cycle(DIST4, 0)
        self.assertEqual(cost, 14)
        self.assertEqual(path, [0, 1, 2, 3, 0])

    def test_cycle_too_few_points(self):
        with self.assertRaises(GraphErro):
            MaskDp(1).shortest_cycle([[0]], 0)

    def test_cycle_tie_takes_lexicographically_smallest(self):
        dist = [[0, 1, 1], [1, 0, 1], [1, 1, 0]]
        cost, path = MaskDp(3).shortest_cycle(dist, 0)
        self.assertEqual(cost, 3)
        self.assertEqual(path, [0, 1, 2, 0])


class TestCoverBaseline(unittest.TestCase):
    def setUp(self):
        self.k = MaskDp(4)

    def test_empty_target_is_zero(self):
        self.assertEqual(self.k.min_cover(0, [0b0011]), (0, []))

    def test_single_subset_covers(self):
        self.assertEqual(self.k.min_cover(0b0011, [0b0011, 0b1100]), (1, [0]))

    def test_two_subsets_needed(self):
        self.assertEqual(self.k.min_cover(0b1111, [0b0011, 0b0100, 0b1100]), (2, [0, 2]))

    def test_three_subsets_needed(self):
        self.assertEqual(self.k.min_cover(0b0111, [0b0001, 0b0010, 0b0100]), (3, [0, 1, 2]))

    def test_tie_takes_lexicographically_smallest(self):
        cnt, chosen = self.k.min_cover(0b0011, [0b0011, 0b0011])
        self.assertEqual((cnt, chosen), (1, [0]))

    def test_no_solution_raises(self):
        with self.assertRaises(CoverErro):
            self.k.min_cover(0b1000, [0b0001, 0b0010])

    def test_cover_visits_positive(self):
        self.k.min_cover(0b1111, [0b0001, 0b0010, 0b0100, 0b1000])
        self.assertGreater(self.k.cover_visits, 0)

    def test_target_out_of_range_raises(self):
        with self.assertRaises(CoverErro):
            self.k.min_cover(0b10000, [0b0001])

    def test_subset_out_of_range_raises(self):
        with self.assertRaises(CoverErro):
            self.k.min_cover(0b0001, [0b10000])

    def test_backtrack_matches(self):
        a = self.k.min_cover(0b1111, [0b0011, 0b0100, 0b1000])
        k2 = MaskDp(4)
        b = k2.min_cover_backtrack(0b1111, [0b0011, 0b0100, 0b1000])
        self.assertEqual(a, b)

    def test_backtrack_no_solution_raises(self):
        with self.assertRaises(CoverErro):
            self.k.min_cover_backtrack(0b1000, [0b0001, 0b0010])


class TestGroupBaseline(unittest.TestCase):
    def setUp(self):
        self.k = MaskDp(3)

    def test_all_compatible_is_one_group(self):
        related = [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
        groups, part = self.k.min_groups(related)
        self.assertEqual(groups, 1)
        self.assertEqual(part, [[0, 1, 2]])

    def test_no_compatible_is_three_groups(self):
        related = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        groups, part = self.k.min_groups(related)
        self.assertEqual(groups, 3)
        self.assertEqual(part, [[0], [1], [2]])

    def test_pair_and_single(self):
        related = [[1, 1, 0], [1, 1, 0], [0, 0, 1]]
        groups, part = self.k.min_groups(related)
        self.assertEqual(groups, 2)
        self.assertEqual(part, [[0, 1], [2]])

    def test_chain_needs_two_groups(self):
        related = [[1, 1, 0], [1, 1, 1], [0, 1, 1]]
        groups, part = self.k.min_groups(related)
        self.assertEqual(groups, 2)
        self.assertEqual(part, [[0], [1, 2]])

    def test_single_element(self):
        groups, part = MaskDp(1).min_groups([[1]])
        self.assertEqual((groups, part), (1, [[0]]))

    def test_zero_elements(self):
        groups, part = MaskDp(0).min_groups([])
        self.assertEqual((groups, part), (0, []))

    def test_partition_visits_positive(self):
        related = [[1, 1, 0], [1, 1, 1], [0, 1, 1]]
        self.k.min_groups(related)
        self.assertGreater(self.k.partition_visits, 0)

    def test_asymmetric_raises(self):
        related = [[1, 1, 0], [0, 1, 0], [0, 0, 1]]
        with self.assertRaises(GraphErro):
            self.k.min_groups(related)

    def test_diagonal_zero_raises(self):
        related = [[0, 1], [1, 0]]
        with self.assertRaises(GraphErro):
            MaskDp(2).min_groups(related)

    def test_bad_value_raises(self):
        related = [[1, 2], [2, 1]]
        with self.assertRaises(GraphErro):
            MaskDp(2).min_groups(related)

    def test_backtrack_matches(self):
        related = [[1, 1, 0], [1, 1, 1], [0, 1, 1]]
        a = self.k.min_groups(related)
        k2 = MaskDp(3)
        b = k2.min_groups_backtrack(related)
        self.assertEqual(a, b)


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        k1 = MaskDp(4)
        k2 = MaskDp(4)
        self.assertEqual(k1.shortest_hamiltonian(DIST4, 0), k2.shortest_hamiltonian(DIST4, 0))
        self.assertEqual(k1.shortest_cycle(DIST4, 0), k2.shortest_cycle(DIST4, 0))
        subsets = [0b0011, 0b0100, 0b1000]
        self.assertEqual(k1.min_cover(0b1111, subsets), k2.min_cover(0b1111, subsets))

    def test_counts_reset_between_calls(self):
        k = MaskDp(4)
        k.shortest_hamiltonian(DIST4, 0)
        first = k.perm_visits
        k.shortest_hamiltonian(DIST4, 0)
        self.assertEqual(k.perm_visits, first)

    def test_fresh_instance_has_zero_counts(self):
        k = MaskDp(4)
        self.assertEqual(k.perm_visits, 0)
        self.assertEqual(k.cover_visits, 0)
        self.assertEqual(k.partition_visits, 0)
        self.assertEqual(k.backtrack_visits, 0)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(SizeErro, Erro))
        self.assertTrue(issubclass(GraphErro, Erro))
        self.assertTrue(issubclass(WeightErro, Erro))
        self.assertTrue(issubclass(CoverErro, Erro))
        self.assertTrue(issubclass(Erro, Exception))


if __name__ == "__main__":
    unittest.main()
