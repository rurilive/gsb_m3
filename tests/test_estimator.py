"""CardinalityEstimator 行为测试，固定种子锁定估算结果。"""

import unittest

from radixest import CardinalityEstimator


BITS = 8192


def _fill(estimator, count, prefix="k"):
    for i in range(count):
        estimator.add(f"{prefix}-{i}")


class TestExactSegment(unittest.TestCase):
    def test_empty_estimator_counts_zero(self):
        e = CardinalityEstimator(bits=BITS, seed=0, exact_limit=64)
        self.assertEqual(e.count(), 0)
        self.assertTrue(e.is_exact())
        self.assertEqual(e.representation(), "exact")
        self.assertEqual(e.error_bound(), 0.0)

    def test_add_reports_new_or_duplicate_while_exact(self):
        e = CardinalityEstimator(bits=BITS, seed=0, exact_limit=64)
        self.assertTrue(e.add("u1"))
        self.assertFalse(e.add("u1"))
        self.assertEqual(e.count(), 1)

    def test_exact_count_obeys_set_equality(self):
        e = CardinalityEstimator(bits=BITS, seed=0, exact_limit=64)
        e.add(1)
        e.add(1.0)
        self.assertEqual(e.count(), 1)
        e.add("1")
        e.add(b"1")
        e.add((1,))
        self.assertEqual(e.count(), 4)

    def test_count_exact_up_to_exact_limit(self):
        e = CardinalityEstimator(bits=BITS, seed=0, exact_limit=100)
        _fill(e, 100)
        self.assertEqual(e.count(), 100)
        self.assertTrue(e.is_exact())

    def test_unhashable_key_raises(self):
        e = CardinalityEstimator(bits=BITS, seed=0, exact_limit=64)
        with self.assertRaises(TypeError):
            e.add(["not", "hashable"])


class TestEstimation(unittest.TestCase):
    def test_promotion_happens_one_key_past_limit(self):
        e = CardinalityEstimator(bits=BITS, seed=0, exact_limit=100, sparse_max=100000)
        _fill(e, 100)
        self.assertTrue(e.is_exact())
        self.assertIsNone(e.add("k-100"))
        self.assertFalse(e.is_exact())
        self.assertEqual(e.representation(), "sparse")
        self.assertGreater(e.error_bound(), 0.0)

    def test_fixed_seed_estimates_are_locked(self):
        expected = {
            (0, 1000): 1011,
            (0, 2000): 1997,
            (0, 3000): 3017,
            (7, 1000): 1000,
            (7, 2000): 2016,
            (7, 3000): 2990,
            (42, 1000): 1003,
            (42, 2000): 2004,
            (42, 3000): 2993,
        }
        for (seed, n), estimate in expected.items():
            e = CardinalityEstimator(bits=BITS, seed=seed, exact_limit=0)
            _fill(e, n)
            self.assertEqual(e.count(), estimate, f"seed={seed} n={n}")

    def test_estimate_stays_within_error_bound(self):
        for seed in range(10):
            for n in (500, 1500, 2500, 3500):
                e = CardinalityEstimator(bits=BITS, seed=seed, exact_limit=0)
                _fill(e, n)
                relative_error = abs(e.count() - n) / n
                self.assertLessEqual(
                    relative_error,
                    e.error_bound(),
                    f"seed={seed} n={n} est={e.count()} bound={e.error_bound()}",
                )

    def test_duplicates_do_not_inflate_estimate(self):
        e = CardinalityEstimator(bits=BITS, seed=7, exact_limit=0)
        for i in range(4000):
            e.add(f"k-{i % 500}")
        self.assertLessEqual(abs(e.count() - 500) / 500, e.error_bound())
        self.assertLess(e.count(), 600)

    def test_same_seed_same_result_different_seed_also_valid(self):
        a = CardinalityEstimator(bits=BITS, seed=7, exact_limit=0)
        b = CardinalityEstimator(bits=BITS, seed=7, exact_limit=0)
        _fill(a, 2000)
        _fill(b, 2000)
        self.assertEqual(a.count(), b.count())

        c = CardinalityEstimator(bits=BITS, seed=123, exact_limit=0)
        _fill(c, 2000)
        self.assertLessEqual(abs(c.count() - 2000) / 2000, c.error_bound())


class TestRepresentations(unittest.TestCase):
    def test_explicit_conversions_keep_count_stable(self):
        e = CardinalityEstimator(bits=BITS, seed=0, exact_limit=100, sparse_max=100000)
        _fill(e, 500)
        self.assertEqual(e.representation(), "sparse")
        sparse_count = e.count()

        self.assertIs(e.to_dense(), e)
        self.assertEqual(e.representation(), "dense")
        dense_count = e.count()
        self.assertEqual(dense_count, sparse_count)

        self.assertIs(e.to_sparse(), e)
        self.assertEqual(e.representation(), "sparse")
        self.assertEqual(e.count(), dense_count)

        e.to_dense().to_sparse().to_dense()
        self.assertEqual(e.representation(), "dense")
        self.assertEqual(e.count(), sparse_count)

    def test_sparse_and_dense_bitmaps_stay_in_sync(self):
        sparse = CardinalityEstimator(bits=BITS, seed=9, exact_limit=0, sparse_max=100000)
        dense = CardinalityEstimator(bits=BITS, seed=9, exact_limit=0, sparse_max=100000)
        dense.add("force-promote")
        dense.to_dense()
        _fill(sparse, 1200)
        _fill(dense, 1200)
        sparse.add("force-promote")
        self.assertEqual(sparse.representation(), "sparse")
        self.assertEqual(dense.representation(), "dense")
        self.assertEqual(sparse.count(), dense.count())

    def test_auto_promotes_to_dense_past_threshold(self):
        reference = CardinalityEstimator(bits=BITS, seed=3, exact_limit=0, sparse_max=100000)
        e = CardinalityEstimator(bits=BITS, seed=3, exact_limit=0, sparse_max=200)
        saw_sparse = False
        for i in range(600):
            e.add(f"k-{i}")
            reference.add(f"k-{i}")
            if e.representation() == "sparse":
                saw_sparse = True
            self.assertEqual(e.count(), reference.count())
        self.assertTrue(saw_sparse)
        self.assertEqual(e.representation(), "dense")

    def test_threshold_zero_means_always_dense(self):
        e = CardinalityEstimator(bits=BITS, seed=0, exact_limit=0, sparse_max=0)
        e.add("k-0")
        self.assertEqual(e.representation(), "dense")


class TestMerge(unittest.TestCase):
    def test_merge_covers_union_without_touching_sources(self):
        a = CardinalityEstimator(bits=BITS, seed=1, exact_limit=0)
        b = CardinalityEstimator(bits=BITS, seed=1, exact_limit=0)
        for i in range(2000):
            a.add(f"k-{i}")
        for i in range(1000, 3000):
            b.add(f"k-{i}")

        union = CardinalityEstimator(bits=BITS, seed=1, exact_limit=0)
        for i in range(3000):
            union.add(f"k-{i}")

        a_before, b_before = a.count(), b.count()
        merged = a.merge(b)
        self.assertEqual(a.count(), a_before)
        self.assertEqual(b.count(), b_before)
        self.assertEqual(merged.count(), union.count())
        self.assertLessEqual(
            abs(merged.count() - 3000) / 3000, merged.error_bound()
        )

    def test_merge_is_symmetric_and_associative(self):
        a = CardinalityEstimator(bits=BITS, seed=5, exact_limit=0)
        b = CardinalityEstimator(bits=BITS, seed=5, exact_limit=0)
        c = CardinalityEstimator(bits=BITS, seed=5, exact_limit=0)
        _fill(a, 800, "a")
        _fill(b, 800, "b")
        _fill(c, 800, "c")
        self.assertEqual(a.merge(b).count(), b.merge(a).count())
        self.assertEqual(
            a.merge(b).merge(c).count(), a.merge(b.merge(c)).count()
        )

    def test_merge_exact_segments_stays_exact(self):
        a = CardinalityEstimator(bits=BITS, seed=1, exact_limit=100)
        b = CardinalityEstimator(bits=BITS, seed=1, exact_limit=100)
        for i in range(60):
            a.add(i)
        for i in range(40, 90):
            b.add(i)
        merged = a.merge(b)
        self.assertTrue(merged.is_exact())
        self.assertEqual(merged.count(), 90)
        self.assertEqual(a.count(), 60)
        self.assertEqual(b.count(), 50)

    def test_merge_exact_with_estimated_uses_bitmap(self):
        a = CardinalityEstimator(bits=BITS, seed=1, exact_limit=50)
        b = CardinalityEstimator(bits=BITS, seed=1, exact_limit=50)
        _fill(a, 40)
        _fill(b, 200)
        self.assertTrue(a.is_exact())
        self.assertFalse(b.is_exact())
        merged = a.merge(b)
        self.assertFalse(merged.is_exact())

        union = CardinalityEstimator(bits=BITS, seed=1, exact_limit=0)
        _fill(union, 200)
        self.assertEqual(merged.count(), union.count())

    def test_merge_works_with_dense_and_sparse_mix(self):
        a = CardinalityEstimator(bits=BITS, seed=2, exact_limit=0, sparse_max=100)
        b = CardinalityEstimator(bits=BITS, seed=2, exact_limit=0, sparse_max=100000)
        _fill(a, 500)
        _fill(b, 500, "other")
        self.assertEqual(a.representation(), "dense")
        self.assertEqual(b.representation(), "sparse")
        merged = a.merge(b)
        self.assertEqual(merged.representation(), "dense")

        union = CardinalityEstimator(bits=BITS, seed=2, exact_limit=0, sparse_max=0)
        _fill(union, 500)
        _fill(union, 500, "other")
        self.assertEqual(merged.count(), union.count())

    def test_merge_rejects_mismatched_config(self):
        a = CardinalityEstimator(bits=BITS, seed=0, exact_limit=0)
        b = CardinalityEstimator(bits=4096, seed=0, exact_limit=0)
        c = CardinalityEstimator(bits=BITS, seed=9, exact_limit=0)
        with self.assertRaises(ValueError):
            a.merge(b)
        with self.assertRaises(ValueError):
            a.merge(c)
        with self.assertRaises(TypeError):
            a.merge(object())


if __name__ == "__main__":
    unittest.main()
