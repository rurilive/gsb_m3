import unittest

from qsketch import EmptySetError, SampleSet, SketchError


class AddTest(unittest.TestCase):
    def test_int_and_float_become_float(self):
        samples = SampleSet()
        self.assertEqual(samples.add(3), 1)
        self.assertEqual(samples.add(2.5), 2)
        self.assertEqual(samples.values(), [3.0, 2.5])

    def test_rejects_non_numeric(self):
        samples = SampleSet()
        for bad in ("12", None, [1], (1,), {"x": 1}):
            with self.assertRaises(SketchError):
                samples.add(bad)
        self.assertEqual(samples.count(), 0)

    def test_rejects_bool(self):
        samples = SampleSet()
        for bad in (True, False):
            with self.assertRaises(SketchError):
                samples.add(bad)

    def test_rejects_non_finite(self):
        samples = SampleSet()
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(SketchError):
                samples.add(bad)


class QuantileTest(unittest.TestCase):
    def test_two_samples_interpolate(self):
        samples = SampleSet([0, 10])
        self.assertEqual(samples.quantile(0.0), 0.0)
        self.assertEqual(samples.quantile(0.25), 2.5)
        self.assertEqual(samples.quantile(0.5), 5.0)
        self.assertEqual(samples.quantile(1.0), 10.0)

    def test_odd_count_middle(self):
        samples = SampleSet([1, 2, 3, 4, 5])
        self.assertEqual(samples.quantile(0.5), 3.0)
        self.assertEqual(samples.quantile(0.25), 2.0)
        self.assertEqual(samples.quantile(0.75), 4.0)

    def test_single_sample_any_q(self):
        samples = SampleSet([7])
        for q in (0.0, 0.5, 0.99, 1.0):
            self.assertEqual(samples.quantile(q), 7.0)

    def test_order_does_not_matter(self):
        a = SampleSet([3, 1, 2])
        b = SampleSet([2, 3, 1])
        for q in (0.1, 0.3, 0.5, 0.9):
            self.assertEqual(a.quantile(q), b.quantile(q))

    def test_duplicates(self):
        samples = SampleSet([5] * 8)
        self.assertEqual(samples.quantile(0.0), 5.0)
        self.assertEqual(samples.quantile(0.5), 5.0)
        self.assertEqual(samples.quantile(1.0), 5.0)

    def test_out_of_range(self):
        samples = SampleSet([1, 2])
        for q in (-0.001, 1.001, 2):
            with self.assertRaises(SketchError):
                samples.quantile(q)

    def test_bad_q_type(self):
        samples = SampleSet([1, 2])
        for q in ("0.5", None, True):
            with self.assertRaises(SketchError):
                samples.quantile(q)

    def test_empty_raises(self):
        with self.assertRaises(EmptySetError):
            SampleSet().quantile(0.5)


class SummaryTest(unittest.TestCase):
    def test_stats(self):
        samples = SampleSet([4, 1, 3, 2])
        self.assertEqual(
            samples.stats(),
            {"count": 4, "mean": 2.5, "min": 1.0, "max": 4.0},
        )

    def test_mean_min_max(self):
        samples = SampleSet([4, 1, 3, 2])
        self.assertEqual(samples.mean(), 2.5)
        self.assertEqual(samples.minimum(), 1.0)
        self.assertEqual(samples.maximum(), 4.0)

    def test_cdf(self):
        samples = SampleSet([1, 2, 3, 4])
        self.assertEqual(samples.cdf(0), 0.0)
        self.assertEqual(samples.cdf(1), 0.25)
        self.assertEqual(samples.cdf(1.5), 0.25)
        self.assertEqual(samples.cdf(2), 0.5)
        self.assertEqual(samples.cdf(9), 1.0)

    def test_cdf_rejects_bad_x(self):
        samples = SampleSet([1])
        for bad in ("x", None, float("inf")):
            with self.assertRaises(SketchError):
                samples.cdf(bad)

    def test_empty_summary_raises(self):
        samples = SampleSet()
        for call in (samples.mean, samples.minimum, samples.maximum, samples.stats):
            with self.assertRaises(EmptySetError):
                call()
        with self.assertRaises(EmptySetError):
            samples.cdf(1)


class MergeTest(unittest.TestCase):
    def test_merge_matches_full(self):
        a = SampleSet([1, 3, 5])
        b = SampleSet([2, 4, 6])
        merged = a.merge(b)
        full = SampleSet([1, 2, 3, 4, 5, 6])
        self.assertEqual(sorted(merged.values()), full.values())
        for q in (0.0, 0.25, 0.5, 0.9, 1.0):
            self.assertEqual(merged.quantile(q), full.quantile(q))

    def test_merge_leaves_inputs_alone(self):
        a = SampleSet([1])
        b = SampleSet([2, 3])
        a.merge(b)
        self.assertEqual(a.values(), [1.0])
        self.assertEqual(b.values(), [2.0, 3.0])

    def test_merge_type_checked(self):
        with self.assertRaises(SketchError):
            SampleSet([1]).merge([2])


if __name__ == "__main__":
    unittest.main()
