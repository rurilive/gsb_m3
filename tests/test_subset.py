"""BitBag 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from bitpackx.subset import BitBag, BitpackError, InvalidValueError


class TestBitBag(unittest.TestCase):
    def test_empty_set_reaches_only_zero(self):
        bag = BitBag()
        self.assertTrue(bag.reachable(0))
        self.assertFalse(bag.reachable(1))
        self.assertEqual(bag.reachable_set(10), [0])
        self.assertEqual(bag.count(10), 1)
        self.assertEqual(bag.max2(10), 0)

    def test_single_element(self):
        bag = BitBag([5])
        self.assertTrue(bag.reachable(5))
        self.assertFalse(bag.reachable(4))
        self.assertEqual(bag.reachable_set(5), [0, 5])
        self.assertEqual(bag.count(5), 2)
        self.assertEqual(bag.max2(5), 5)

    def test_default_items_subsets(self):
        bag = BitBag([2, 3])
        self.assertEqual(bag.reachable_set(5), [0, 2, 3, 5])
        self.assertTrue(bag.reachable(2))
        self.assertTrue(bag.reachable(3))
        self.assertTrue(bag.reachable(5))
        self.assertFalse(bag.reachable(1))
        self.assertFalse(bag.reachable(4))

    def test_repeated_values(self):
        bag = BitBag([3, 3])
        self.assertTrue(bag.reachable(6))
        self.assertEqual(bag.reachable_set(6), [0, 3, 6])

    def test_count_matches_reachable_set(self):
        bag = BitBag([1, 4, 6])
        for limit in range(0, 12):
            self.assertEqual(bag.count(limit), len(bag.reachable_set(limit)))

    def test_max2_picks_largest(self):
        bag = BitBag([3, 7, 11])
        self.assertEqual(bag.max2(10), 10)
        self.assertEqual(bag.max2(2), 0)
        self.assertEqual(bag.max2(0), 0)

    def test_target_zero_is_true(self):
        self.assertTrue(BitBag([2, 3]).reachable(0))

    def test_target_beyond_sum(self):
        bag = BitBag([2, 3])
        self.assertFalse(bag.reachable(9))
        self.assertEqual(bag.max2(9), 5)

    def test_items_returns_copy(self):
        bag = BitBag([1, 1])
        got = bag.items()
        got.append(9)
        self.assertEqual(bag.items(), [1, 1])

    def test_add_is_chainable(self):
        bag = BitBag().add(2).add(4)
        self.assertTrue(bag.reachable(6))

    def test_negative_item_rejected(self):
        with self.assertRaises(InvalidValueError):
            BitBag([-1])

    def test_zero_item_rejected(self):
        with self.assertRaises(InvalidValueError):
            BitBag([0])

    def test_non_integer_rejected(self):
        with self.assertRaises(InvalidValueError):
            BitBag([1.5])

    def test_error_base_class(self):
        self.assertTrue(issubclass(InvalidValueError, BitpackError))
        self.assertTrue(issubclass(BitpackError, Exception))

    def test_negative_target_rejected(self):
        with self.assertRaises(InvalidValueError):
            BitBag([1]).reachable(-2)

    def test_negative_limit_rejected(self):
        with self.assertRaises(InvalidValueError):
            BitBag([1]).reachable_set(-1)

    def test_deterministic_repeat(self):
        bag = BitBag([2, 3, 5])
        self.assertEqual(bag.reachable_set(10), bag.reachable_set(10))


if __name__ == "__main__":
    unittest.main()
