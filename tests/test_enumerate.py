"""基线测试：锁住 NaiveEnumerator 的现状行为。

这是改造前的基线，一字不许改，必须始终全绿。
"""

import unittest

from combperm.enumerate import CombPermError, NaiveEnumerator


class TestConstruction(unittest.TestCase):
    def test_size_kept(self):
        self.assertEqual(NaiveEnumerator(4).size(), 4)

    def test_zero_size_ok(self):
        self.assertEqual(NaiveEnumerator(0).size(), 0)

    def test_bad_size_rejected(self):
        for bad in (-1, 1.5, "3", None, True):
            with self.assertRaises(CombPermError):
                NaiveEnumerator(bad)


class TestCounts(unittest.TestCase):
    def test_combination_count(self):
        e = NaiveEnumerator(4)
        self.assertEqual(e.combinations_count(0), 1)
        self.assertEqual(e.combinations_count(1), 4)
        self.assertEqual(e.combinations_count(2), 6)
        self.assertEqual(e.combinations_count(4), 1)

    def test_permutation_count(self):
        e = NaiveEnumerator(4)
        self.assertEqual(e.permutations_count(0), 1)
        self.assertEqual(e.permutations_count(1), 4)
        self.assertEqual(e.permutations_count(2), 12)
        self.assertEqual(e.permutations_count(4), 24)

    def test_bad_k_rejected(self):
        e = NaiveEnumerator(3)
        for bad in (-1, 4, 1.5, "2", None, True):
            with self.assertRaises(CombPermError):
                e.combinations_count(bad)
            with self.assertRaises(CombPermError):
                e.permutations_count(bad)


class TestEnumerate(unittest.TestCase):
    def test_all_combinations_lexicographic(self):
        e = NaiveEnumerator(4)
        self.assertEqual(
            e.all_combinations(2),
            [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
        )

    def test_all_permutations_lexicographic(self):
        e = NaiveEnumerator(3)
        self.assertEqual(
            e.all_permutations(3),
            [
                (0, 1, 2),
                (0, 2, 1),
                (1, 0, 2),
                (1, 2, 0),
                (2, 0, 1),
                (2, 1, 0),
            ],
        )

    def test_empty_combination(self):
        e = NaiveEnumerator(3)
        self.assertEqual(e.all_combinations(0), [()])

    def test_permutations_length_two(self):
        e = NaiveEnumerator(3)
        self.assertEqual(
            e.all_permutations(2),
            [(0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1)],
        )


class TestNthAndRank(unittest.TestCase):
    def test_nth_permutation(self):
        e = NaiveEnumerator(4)
        self.assertEqual(e.nth(4, 0, "perm"), (0, 1, 2, 3))
        self.assertEqual(e.nth(4, 5, "perm"), (0, 3, 2, 1))
        self.assertEqual(e.nth(4, 23, "perm"), (3, 2, 1, 0))

    def test_nth_combination(self):
        e = NaiveEnumerator(4)
        self.assertEqual(e.nth(2, 0, "comb"), (0, 1))
        self.assertEqual(e.nth(2, 4, "comb"), (1, 3))
        self.assertEqual(e.nth(2, 5, "comb"), (2, 3))

    def test_rank_permutation(self):
        e = NaiveEnumerator(4)
        self.assertEqual(e.rank((0, 1, 2, 3), "perm"), 0)
        self.assertEqual(e.rank((0, 3, 2, 1), "perm"), 5)
        self.assertEqual(e.rank((3, 2, 1, 0), "perm"), 23)

    def test_rank_combination(self):
        e = NaiveEnumerator(4)
        self.assertEqual(e.rank((0, 1), "comb"), 0)
        self.assertEqual(e.rank((1, 3), "comb"), 4)
        self.assertEqual(e.rank((2, 3), "comb"), 5)

    def test_nth_rank_roundtrip(self):
        e = NaiveEnumerator(4)
        for i in range(24):
            self.assertEqual(e.rank(e.nth(4, i, "perm"), "perm"), i)

    def test_bad_mode_rejected(self):
        e = NaiveEnumerator(3)
        with self.assertRaises(CombPermError):
            e.nth(3, 0, "nope")
        with self.assertRaises(CombPermError):
            e.rank((0, 1, 2), "nope")

    def test_out_of_range_index_rejected(self):
        e = NaiveEnumerator(3)
        for bad in (-1, 6, 100):
            with self.assertRaises(CombPermError):
                e.nth(3, bad, "perm")

    def test_bad_index_type_rejected(self):
        e = NaiveEnumerator(3)
        for bad in (0.5, "0", None, True):
            with self.assertRaises(CombPermError):
                e.nth(3, bad, "perm")

    def test_bad_sequence_rejected(self):
        e = NaiveEnumerator(3)
        with self.assertRaises(CombPermError):
            e.rank("012", "perm")
        with self.assertRaises(CombPermError):
            e.rank((0, 3, 1), "perm")
        with self.assertRaises(CombPermError):
            e.rank((0, 0, 1), "perm")
        with self.assertRaises(CombPermError):
            e.rank((1.0, 2.0), "perm")
        with self.assertRaises(CombPermError):
            e.rank((1, 2, 0), "comb")


if __name__ == "__main__":
    unittest.main()
