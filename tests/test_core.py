"""基线测试：锁住 NaiveCoinChange 的现状行为。

这是改造前的基线，一字不许改，必须始终全绿。
"""

import unittest

from coinchange.core import NaiveCoinChange, CoinChangeError


class TestConstruction(unittest.TestCase):
    def test_length_counts_denominations(self):
        self.assertEqual(len(NaiveCoinChange([1, 2, 5], 11)), 3)

    def test_target_is_readable(self):
        self.assertEqual(NaiveCoinChange([1], 7).target, 7)

    def test_coins_are_sorted_and_deduped(self):
        self.assertEqual(NaiveCoinChange([5, 1, 2, 1, 5], 11).coins, [1, 2, 5])

    def test_coins_property_is_a_copy(self):
        c = NaiveCoinChange([1, 2], 5)
        c.coins.append(99)
        self.assertEqual(c.coins, [1, 2])

    def test_non_integer_coin_rejected(self):
        for bad in (1.5, "1", None, True):
            with self.assertRaises(CoinChangeError):
                NaiveCoinChange([bad], 5)

    def test_non_positive_coin_rejected(self):
        for bad in (0, -1):
            with self.assertRaises(CoinChangeError):
                NaiveCoinChange([bad], 5)

    def test_non_integer_target_rejected(self):
        for bad in (1.5, "5", None, True):
            with self.assertRaises(CoinChangeError):
                NaiveCoinChange([1], bad)

    def test_negative_target_rejected(self):
        with self.assertRaises(CoinChangeError):
            NaiveCoinChange([1], -1)


class TestMinCoins(unittest.TestCase):
    def test_classic_instance(self):
        self.assertEqual(NaiveCoinChange([1, 2, 5], 11).min_coins(), 3)

    def test_single_coin_exact(self):
        self.assertEqual(NaiveCoinChange([5], 10).min_coins(), 2)

    def test_single_coin_not_dividing_target_unreachable(self):
        self.assertEqual(NaiveCoinChange([4], 6).min_coins(), NaiveCoinChange._UNREACHABLE)

    def test_zero_target_needs_zero_coins(self):
        self.assertEqual(NaiveCoinChange([1, 2], 0).min_coins(), 0)

    def test_empty_coins_nonzero_target_unreachable(self):
        self.assertEqual(NaiveCoinChange([], 5).min_coins(), NaiveCoinChange._UNREACHABLE)

    def test_empty_coins_zero_target_is_zero(self):
        self.assertEqual(NaiveCoinChange([], 0).min_coins(), 0)

    def test_greedy_would_be_wrong_but_naive_is_correct(self):
        # 面值 1、3、4，目标 6：贪心取 4 后剩 2 需两枚 1，共三枚；
        # 最优是 3 加 3 共两枚，朴素枚举能取到最优
        self.assertEqual(NaiveCoinChange([1, 3, 4], 6).min_coins(), 2)


class TestReachability(unittest.TestCase):
    def test_reachable_true(self):
        self.assertTrue(NaiveCoinChange([1, 2, 5], 11).is_reachable())

    def test_unreachable_false(self):
        self.assertFalse(NaiveCoinChange([2, 4], 3).is_reachable())

    def test_zero_target_reachable(self):
        self.assertTrue(NaiveCoinChange([2, 4], 0).is_reachable())

    def test_reachable_matches_min_coins(self):
        c = NaiveCoinChange([3, 5], 7)
        self.assertEqual(c.is_reachable(), c.min_coins() < NaiveCoinChange._UNREACHABLE)


class TestSelection(unittest.TestCase):
    def test_selection_sums_to_target(self):
        c = NaiveCoinChange([1, 2, 5], 11)
        self.assertEqual(sum(c.selection()), c.target)

    def test_selection_length_equals_min_coins(self):
        c = NaiveCoinChange([1, 2, 5], 11)
        self.assertEqual(len(c.selection()), c.min_coins())

    def test_selection_is_sorted(self):
        self.assertEqual(NaiveCoinChange([5, 1, 2], 11).selection(), [1, 5, 5])

    def test_selection_prefers_smaller_coin_first(self):
        # 目标 4，面值 1、3：只有一种最优取法 [1, 3]
        self.assertEqual(NaiveCoinChange([1, 3], 4).selection(), [1, 3])

    def test_selection_unreachable_is_empty(self):
        self.assertEqual(NaiveCoinChange([2, 4], 3).selection(), [])

    def test_selection_zero_target_is_empty(self):
        self.assertEqual(NaiveCoinChange([1, 2], 0).selection(), [])


class TestCountMinWays(unittest.TestCase):
    def test_classic_count(self):
        # 目标 11，最少三枚：1 加 5 加 5 与 1 加 …，唯一最优取法是 [1,5,5]
        self.assertEqual(NaiveCoinChange([1, 2, 5], 11).count_min_ways(), 1)

    def test_two_optimal_ways(self):
        # 目标 4，面值 1、2、3：最少两枚，取法为 [1,3] 与 [2,2]，共两条
        self.assertEqual(NaiveCoinChange([1, 2, 3], 4).count_min_ways(), 2)

    def test_ways_are_multisets_not_orders(self):
        # 目标 3，面值 1、2：只有 [1,2] 一种最优取法，不许把 [2,1] 另算一条
        self.assertEqual(NaiveCoinChange([1, 2], 3).count_min_ways(), 1)

    def test_unreachable_has_zero_ways(self):
        self.assertEqual(NaiveCoinChange([2, 4], 3).count_min_ways(), 0)

    def test_zero_target_has_one_empty_way(self):
        self.assertEqual(NaiveCoinChange([1, 2], 0).count_min_ways(), 1)

    def test_duplicate_denominations_are_merged(self):
        # 重复面值按规范口径去重，[1,1,2] 与 [1,2] 同口径
        self.assertEqual(
            NaiveCoinChange([1, 1, 2], 3).count_min_ways(),
            NaiveCoinChange([1, 2], 3).count_min_ways(),
        )


class TestErrorBase(unittest.TestCase):
    def test_error_inherits_exception(self):
        self.assertTrue(issubclass(CoinChangeError, Exception))

    def test_error_can_be_caught_by_base(self):
        with self.assertRaises(CoinChangeError):
            NaiveCoinChange([0], 5)


if __name__ == "__main__":
    unittest.main()
