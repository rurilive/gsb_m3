"""permparity 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from permparity import (
    PermParityError,
    InvalidPermutationError,
    UnsupportedElementError,
    validate_perm,
    inversion_count,
    parity,
    is_even,
    cycle_decomposition,
    min_swaps,
    cycle_type,
    parity_by_cycles,
    compose,
    compose_parity,
    can_swap,
    min_swaps_between,
)


class TestExceptions(unittest.TestCase):
    def test_base_is_exception(self):
        self.assertTrue(issubclass(PermParityError, Exception))

    def test_specific_inherit_base(self):
        self.assertTrue(issubclass(InvalidPermutationError, PermParityError))
        self.assertTrue(issubclass(UnsupportedElementError, PermParityError))

    def test_duplicate_rejected(self):
        with self.assertRaises(InvalidPermutationError):
            validate_perm([0, 0, 2])

    def test_out_of_range_rejected(self):
        with self.assertRaises(InvalidPermutationError):
            validate_perm([1, 2])
        with self.assertRaises(InvalidPermutationError):
            validate_perm([-1, 0])

    def test_non_integer_rejected(self):
        with self.assertRaises(UnsupportedElementError):
            validate_perm([0, "a"])
        with self.assertRaises(UnsupportedElementError):
            validate_perm([0.5, 0])
        with self.assertRaises(UnsupportedElementError):
            validate_perm([True, False])

    def test_non_iterable_rejected(self):
        with self.assertRaises(UnsupportedElementError):
            validate_perm(5)


class TestValidate(unittest.TestCase):
    def test_empty_len(self):
        self.assertEqual(validate_perm([]), [])

    def test_single_ok(self):
        self.assertEqual(validate_perm([0]), [0])

    def test_identity_len(self):
        self.assertEqual(validate_perm([0, 1, 2, 3]), [0, 1, 2, 3])

    def test_returns_plain_list(self):
        self.assertEqual(validate_perm((0, 1, 2)), [0, 1, 2])

    def test_reverse_ok(self):
        self.assertEqual(validate_perm([3, 2, 1, 0]), [3, 2, 1, 0])


class TestInverseCount(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(inversion_count([]), (0, 0))

    def test_single(self):
        self.assertEqual(inversion_count([0]), (0, 0))

    def test_identity(self):
        self.assertEqual(inversion_count([0, 1, 2]), (0, 3))

    def test_reverse_three(self):
        self.assertEqual(inversion_count([2, 1, 0]), (3, 3))

    def test_reverse_four(self):
        self.assertEqual(inversion_count([3, 2, 1, 0]), (6, 6))

    def test_small(self):
        self.assertEqual(inversion_count([2, 0, 1]), (2, 3))

    def test_small_second(self):
        self.assertEqual(inversion_count([1, 2, 0, 3]), (2, 6))

    def test_comparison_is_quadratic(self):
        for n in (2, 3, 4, 5, 6):
            _, comparisons = inversion_count(list(range(n)))
            self.assertEqual(comparisons, n * (n - 1) // 2)


class TestParity(unittest.TestCase):
    def test_empty_even(self):
        self.assertEqual(parity([]), "even")

    def test_identity(self):
        self.assertEqual(parity([0, 1, 2]), "even")
        self.assertEqual(parity([0, 1]), "even")

    def test_reverse(self):
        self.assertEqual(parity([1, 0]), "odd")
        self.assertEqual(parity([2, 1, 0]), "odd")
        self.assertEqual(parity([3, 2, 1, 0]), "even")

    def test_is_even(self):
        self.assertTrue(is_even([2, 0, 1, 3]))
        self.assertFalse(is_even([0, 2, 1, 3]))


class TestCycleDecomposition(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(cycle_decomposition([]), [])

    def test_single_fixed_point(self):
        self.assertEqual(cycle_decomposition([0]), [(0,)])

    def test_identity_all_fixed_points(self):
        self.assertEqual(cycle_decomposition([0, 1, 2, 3]),
                         [(0,), (1,), (2,), (3,)])

    def test_three_cycle(self):
        self.assertEqual(cycle_decomposition([1, 2, 0]), [(0, 1, 2)])

    def test_transposition(self):
        self.assertEqual(cycle_decomposition([1, 0, 2]), [(0, 1), (2,)])

    def test_two_cycles(self):
        self.assertEqual(cycle_decomposition([3, 2, 1, 0]),
                         [(0, 3), (1, 2)])

    def test_cycles_sorted_by_min(self):
        cycles = cycle_decomposition([2, 4, 0, 1, 3])
        self.assertEqual(cycles, [(0, 2), (1, 4, 3)])

    def test_cycle_type(self):
        self.assertEqual(cycle_type([1, 2, 0]), (3,))
        self.assertEqual(cycle_type([1, 0, 2]), (1, 2))
        self.assertEqual(cycle_type([0, 1, 2, 3]), (1, 1, 1, 1))
        self.assertEqual(cycle_type([]), ())


class TestMinSwaps(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(min_swaps([]), 0)

    def test_identity(self):
        self.assertEqual(min_swaps([0, 1, 2, 3]), 0)

    def test_transposition(self):
        self.assertEqual(min_swaps([1, 0, 2]), 1)

    def test_three_cycle(self):
        self.assertEqual(min_swaps([1, 2, 0]), 2)

    def test_two_cycles(self):
        self.assertEqual(min_swaps([3, 2, 1, 0]), 2)


class TestParityByCycles(unittest.TestCase):
    def test_consistent_with_parity(self):
        for perm in ([], [0], [1, 0], [2, 0, 1], [2, 1, 0],
                     [1, 2, 0, 3], [3, 2, 1, 0], [1, 3, 2, 0]):
            self.assertEqual(parity_by_cycles(perm), parity(perm))

    def test_fixed_points_are_even(self):
        self.assertEqual(parity_by_cycles([0, 1, 2, 3]), "even")


class TestCompose(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(compose([0, 1, 2], [2, 0, 1]), [2, 0, 1])
        self.assertEqual(compose([2, 0, 1], [0, 1, 2]), [2, 0, 1])

    def test_specific(self):
        self.assertEqual(compose([1, 0, 2], [0, 2, 1]), [1, 2, 0])

    def test_length_mismatch(self):
        with self.assertRaises(InvalidPermutationError):
            compose([0, 1], [0, 1, 2])

    def test_compose_parity(self):
        self.assertEqual(compose_parity([1, 0], [1, 0]), "even")

    def test_compose_parity_second(self):
        self.assertEqual(compose_parity([1, 0, 2], [0, 2, 1]), "even")


class TestSwapHelpers(unittest.TestCase):
    def test_can_swap_same_length(self):
        self.assertTrue(can_swap([0, 1, 2], [2, 1, 0]))
        self.assertTrue(can_swap([], []))

    def test_can_swap_different_length(self):
        self.assertFalse(can_swap([0, 1], [0, 1, 2]))

    def test_min_swaps_between_identity(self):
        self.assertEqual(min_swaps_between([0, 1, 2], [0, 1, 2]), 0)

    def test_min_swaps_between_reverse(self):
        self.assertEqual(min_swaps_between([2, 0, 1], [0, 1, 2]), 2)

    def test_min_swaps_between_length_mismatch(self):
        with self.assertRaises(InvalidPermutationError):
            min_swaps_between([0, 1], [0, 1, 2])


class TestDeterminism(unittest.TestCase):
    def test_repeat_same_result(self):
        perm = [3, 1, 4, 0, 2]
        first = (inversion_count(perm), parity(perm),
                 cycle_decomposition(perm), min_swaps(perm))
        second = (inversion_count(perm), parity(perm),
                  cycle_decomposition(perm), min_swaps(perm))
        self.assertEqual(first, second)

    def test_input_not_mutated(self):
        perm = [3, 1, 4, 0, 2]
        original = list(perm)
        cycle_decomposition(perm)
        parity(perm)
        min_swaps(perm)
        self.assertEqual(perm, original)


if __name__ == "__main__":
    unittest.main()
