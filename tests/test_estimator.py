"""CardinalityEstimator 行为测试。

固定种子下，count() 在精确段必须精确；进入估算段后，固定种子的偏差不得
超过 error_bound() 给出的相对误差界。位图稀疏/稠密转换 count() 不跳，
merge 产出覆盖并集的新估算器，输入不动。
"""

import threading
import unittest

from radixest import CardinalityEstimator


SEED = 42
BITS = 1 << 16
EXACT_LIMIT = 1000


def make_estimator(**kwargs):
    params = {"bits": BITS, "seed": SEED, "exact_limit": EXACT_LIMIT}
    params.update(kwargs)
    return CardinalityEstimator(**params)


def feed(estimator, count, prefix="key"):
    for i in range(count):
        estimator.add(f"{prefix}-{i}")


class TestExactSegment(unittest.TestCase):
    def test_empty_count_is_zero_with_zero_bound(self):
        est = make_estimator()
        self.assertEqual(est.count(), 0)
        self.assertEqual(est.error_bound(), 0.0)

    def test_count_exact_below_limit(self):
        est = make_estimator()
        feed(est, EXACT_LIMIT)
        self.assertEqual(est.count(), EXACT_LIMIT)
        self.assertEqual(est.error_bound(), 0.0)

    def test_add_reports_newness(self):
        est = make_estimator()
        self.assertTrue(est.add("u1"))
        self.assertFalse(est.add("u1"))
        self.assertEqual(est.count(), 1)

    def test_duplicates_do_not_promote(self):
        est = make_estimator()
        for _ in range(EXACT_LIMIT * 3):
            est.add("same")
        self.assertFalse(est.is_dense)
        self.assertEqual(est.count(), 1)

    def test_set_equal_keys_collapse(self):
        est = make_estimator(exact_limit=100)
        est.add(1)
        est.add(1.0)
        self.assertEqual(est.count(), 1)

    def test_unhashable_key_raises(self):
        est = make_estimator()
        with self.assertRaises(TypeError):
            est.add(["not", "hashable"])

    def test_invalid_construction_params_raise(self):
        with self.assertRaises(ValueError):
            CardinalityEstimator(bits=0, seed=SEED, exact_limit=10)
        with self.assertRaises(ValueError):
            CardinalityEstimator(bits=BITS, seed=SEED, exact_limit=-1)
        with self.assertRaises(ValueError):
            CardinalityEstimator(bits=BITS, seed=SEED, exact_limit=10,
                                 dense_threshold=-1)


class TestEstimation(unittest.TestCase):
    def assert_within_bound(self, est, true_count):
        estimate = est.count()
        bound = est.error_bound()
        relative_error = abs(estimate - true_count) / true_count
        self.assertLessEqual(
            relative_error, bound,
            f"estimate={estimate} true={true_count} rel={relative_error} "
            f"bound={bound}",
        )

    def test_promotion_keeps_exact_base_population(self):
        est = make_estimator()
        feed(est, EXACT_LIMIT + 1)
        self.assertGreater(est.error_bound(), 0.0)  # 已退出精确段
        self.assert_within_bound(est, EXACT_LIMIT + 1)

    def test_fixed_seed_estimate_stays_within_error_bound(self):
        for true_count in (EXACT_LIMIT + 1, 2000, 5000, 10000, 20000):
            est = make_estimator()
            feed(est, true_count)
            self.assert_within_bound(est, true_count)

    def test_fixed_seed_estimate_is_deterministic(self):
        first = make_estimator()
        second = make_estimator()
        feed(first, 12345)
        feed(second, 12345)
        self.assertEqual(first.count(), second.count())

    def test_bound_is_relative_and_positive_after_promotion(self):
        est = make_estimator()
        feed(est, 8000)
        self.assertGreater(est.error_bound(), 0.0)
        self.assertLessEqual(est.error_bound(), 1.0)


class TestBitmapRepresentation(unittest.TestCase):
    def test_auto_promote_to_dense_past_threshold(self):
        est = make_estimator(exact_limit=100, dense_threshold=200)
        feed(est, 1000)
        self.assertTrue(est.is_dense)

    def test_stays_sparse_below_threshold(self):
        est = make_estimator(exact_limit=100, dense_threshold=10000)
        feed(est, 1000)
        self.assertFalse(est.is_dense)

    def test_explicit_conversion_keeps_count_stable(self):
        est = make_estimator(exact_limit=100, dense_threshold=100000)
        feed(est, 3000)
        sparse_count = est.count()
        self.assertFalse(est.is_dense)
        est.to_dense()
        self.assertTrue(est.is_dense)
        dense_count = est.count()
        est.to_dense()  # 幂等
        est.to_sparse()
        self.assertFalse(est.is_dense)
        sparse_again = est.count()
        est.to_sparse()  # 幂等
        self.assertEqual(dense_count, sparse_count)
        self.assertEqual(sparse_again, sparse_count)

    def test_zero_threshold_starts_dense_immediately(self):
        est = make_estimator(exact_limit=10, dense_threshold=0)
        feed(est, 50)
        self.assertTrue(est.is_dense)
        self.assertGreater(est.count(), 0)

    def test_repeated_adds_after_conversion(self):
        est = make_estimator(exact_limit=50, dense_threshold=100)
        feed(est, 500)
        count_before = est.count()
        for i in range(500):
            self.assertFalse(est.add(f"key-{i}"))
        self.assertEqual(est.count(), count_before)


class TestMerge(unittest.TestCase):
    def test_exact_merge_stays_exact(self):
        left = make_estimator(exact_limit=100)
        right = make_estimator(exact_limit=100)
        for key in ("a", "b", "c"):
            left.add(key)
        for key in ("c", "d"):
            right.add(key)
        merged = left.merge(right)
        self.assertEqual(merged.count(), 4)
        self.assertEqual(merged.error_bound(), 0.0)

    def test_merge_inputs_are_not_mutated(self):
        left = make_estimator(exact_limit=50, dense_threshold=100000)
        right = make_estimator(exact_limit=50, dense_threshold=100000)
        feed(left, 1000, prefix="left")
        feed(right, 1000, prefix="right")
        left_count, right_count = left.count(), right.count()
        left_sparse = left.is_dense
        merged = left.merge(right)
        self.assertEqual(left.count(), left_count)
        self.assertEqual(right.count(), right_count)
        self.assertEqual(left.is_dense, left_sparse)
        self.assertGreaterEqual(merged.count(), max(left_count, right_count))

    def test_merge_covers_union_within_bound(self):
        left = make_estimator(exact_limit=500)
        right = make_estimator(exact_limit=500)
        left_keys = {f"k{i}" for i in range(0, 20000, 2)}
        right_keys = {f"k{i}" for i in range(10000, 30000)}
        for key in left_keys:
            left.add(key)
        for key in right_keys:
            right.add(key)
        merged = left.merge(right)
        true_union = len(left_keys | right_keys)
        relative_error = abs(merged.count() - true_union) / true_union
        self.assertLessEqual(relative_error, merged.error_bound())

    def test_merge_exact_with_probabilistic_side(self):
        left = make_estimator(exact_limit=10000)
        right = make_estimator(exact_limit=100)
        feed(left, 200, prefix="small")
        feed(right, 3000, prefix="big")
        merged = left.merge(right)
        self.assertGreater(merged.error_bound(), 0.0)
        self.assertGreater(merged.count(), 2900)

    def test_merge_dense_and_sparse(self):
        sparse = make_estimator(exact_limit=50, dense_threshold=100000)
        dense = make_estimator(exact_limit=50, dense_threshold=100)
        feed(sparse, 800, prefix="s")
        feed(dense, 800, prefix="d")
        merged = sparse.merge(dense)
        self.assertTrue(merged.is_dense)
        self.assertGreater(merged.count(), sparse.count())

    def test_merge_rejects_incompatible_configs(self):
        good = make_estimator()
        other_bits = CardinalityEstimator(BITS * 2, SEED, EXACT_LIMIT)
        other_seed = CardinalityEstimator(BITS, SEED + 1, EXACT_LIMIT)
        with self.assertRaises(ValueError):
            good.merge(other_bits)
        with self.assertRaises(ValueError):
            good.merge(other_seed)
        with self.assertRaises(TypeError):
            good.merge(42)


class TestConcurrency(unittest.TestCase):
    def test_concurrent_adds_do_not_corrupt_state(self):
        est = make_estimator(exact_limit=100000, dense_threshold=100000)

        def worker(base):
            for i in range(300):
                est.add((base, i))

        threads = [
            threading.Thread(target=worker, args=(b,)) for b in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(est.count(), 2400)


if __name__ == "__main__":
    unittest.main()
