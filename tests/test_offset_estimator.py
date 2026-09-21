"""OffsetEstimator 与 OffsetFilter 的验收测试，单独成文件，不动既有基线。

覆盖任务验收口径：已知真值对拍收敛、不对称链路、延迟尖峰与错误样本、
墙钟回拨与前跳压测、上万轮采样不漂不涨。
"""

import time
import unittest

from steadyclock import (
    Deadline,
    Estimate,
    ManualSource,
    OffsetEstimator,
    OffsetFilter,
)
from steadyclock.simclock import Link, Loopback, PeerClock

TRUTH = 2.0
LINK = dict(base_delay=0.02, jitter=0.004)


def make_estimator(truth=TRUTH, seed=42, **link_kwargs):
    source = ManualSource(wall=1_700_000_000.0)
    peer = PeerClock(true_offset=truth)
    link = Link(seed=seed, **link_kwargs)
    return OffsetEstimator(Loopback(source, peer, link)), source, peer


class TestConvergence(unittest.TestCase):
    def test_estimate_carries_the_three_fields(self):
        estimator, _source, _peer = make_estimator()
        estimate = estimator.sample()
        self.assertIsInstance(estimate, Estimate)
        self.assertIsInstance(estimate.offset, float)
        self.assertIsInstance(estimate.error_bound, float)
        self.assertIsInstance(estimate.confidence, float)

    def test_converges_into_tolerance_and_fast(self):
        estimator, _source, _peer = make_estimator()
        converged_at = None
        for round_ in range(200):
            estimate = estimator.sample()
            if estimator.converged:
                converged_at = round_
                break
        self.assertIsNotNone(converged_at)
        self.assertLessEqual(converged_at, 100)
        self.assertAlmostEqual(estimate.offset, TRUTH, delta=0.005)
        self.assertGreaterEqual(estimate.error_bound, abs(estimate.offset - TRUTH))
        self.assertGreater(estimate.confidence, 0.9)

    def test_bound_keeps_covering_truth_while_converging(self):
        estimator, _source, _peer = make_estimator()
        for _ in range(200):
            estimate = estimator.sample()
            self.assertGreaterEqual(
                estimate.error_bound, abs(estimate.offset - TRUTH)
            )

    def test_asymmetric_link_still_converges_and_covers(self):
        skew = 0.01
        estimator, _source, _peer = make_estimator(skew=skew)
        for _ in range(200):
            estimate = estimator.sample()
        self.assertTrue(estimator.converged)
        self.assertAlmostEqual(estimate.offset, TRUTH, delta=skew / 2.0 + 0.005)
        self.assertGreaterEqual(estimate.error_bound, abs(estimate.offset - TRUTH))

    def test_spikes_and_faults_do_not_pull_the_estimate(self):
        estimator, _source, _peer = make_estimator(
            truth=-7.5, spike_chance=0.2, fault_chance=0.1
        )
        for _ in range(200):
            estimate = estimator.sample()
        self.assertTrue(estimator.converged)
        self.assertAlmostEqual(estimate.offset, -7.5, delta=0.005)
        self.assertGreaterEqual(estimate.error_bound, abs(estimate.offset + 7.5))

    def test_dirty_link_lowers_confidence(self):
        clean, _source, _peer = make_estimator()
        dirty, _source2, _peer2 = make_estimator(
            seed=43, spike_chance=0.2, fault_chance=0.1
        )
        for _ in range(100):
            clean_estimate = clean.sample()
            dirty_estimate = dirty.sample()
        self.assertGreater(clean_estimate.confidence, 0.95)
        self.assertLess(dirty_estimate.confidence, clean_estimate.confidence - 0.1)

    def test_locked_estimate_does_not_jitter(self):
        estimator, _source, _peer = make_estimator()
        for _ in range(100):
            estimator.sample()
        locked = estimator.sample()
        for _ in range(500):
            estimate = estimator.sample()
            self.assertEqual(estimate.offset, locked.offset)
            self.assertEqual(estimate.error_bound, locked.error_bound)

    def test_peer_recalibration_is_retracked(self):
        estimator, _source, peer = make_estimator()
        for _ in range(100):
            estimator.sample()
        peer.true_offset = -3.0
        for _ in range(200):
            estimate = estimator.sample()
            if estimator.converged and abs(estimate.offset + 3.0) < 0.005:
                break
        else:
            self.fail("对端重新校时后估计没有跟上")
        self.assertGreaterEqual(estimate.error_bound, abs(estimate.offset + 3.0))


class TestWallClockStress(unittest.TestCase):
    def test_wall_steps_do_not_move_the_estimate(self):
        stepped, stepped_source, _peer = make_estimator()
        plain, _plain_source, _peer2 = make_estimator()
        for round_ in range(300):
            stepped_estimate = stepped.sample()
            plain_estimate = plain.sample()
            if round_ % 2:
                stepped_source.step_wall(-300.0)
            else:
                stepped_source.step_wall(600.0)
            self.assertEqual(stepped_estimate, plain_estimate)

    def test_wall_steps_do_not_move_deadline(self):
        source = ManualSource(wall=1_700_000_000.0)
        deadline = Deadline(source, 5.0)
        source.sleep(1.0)
        before = deadline.remaining()
        source.step_wall(-300.0)
        self.assertAlmostEqual(deadline.remaining(), before)
        self.assertFalse(deadline.expired())
        source.step_wall(600.0)
        self.assertAlmostEqual(deadline.remaining(), before)
        self.assertFalse(deadline.expired())
        source.sleep(before)
        self.assertTrue(deadline.expired())


class TestLongRun(unittest.TestCase):
    ROUNDS = 12000

    def test_no_drift_no_bound_growth_no_slowdown(self):
        estimator, _source, _peer = make_estimator(
            truth=-7.5, spike_chance=0.1, seed=5
        )
        offsets = set()
        bounds = set()
        start = time.perf_counter()
        for round_ in range(self.ROUNDS):
            estimate = estimator.sample()
            if round_ == 999:
                first_block = time.perf_counter() - start
            if round_ >= 100:
                offsets.add(estimate.offset)
                bounds.add(estimate.error_bound)
        remaining = time.perf_counter() - start - first_block
        self.assertEqual(len(offsets), 1)
        self.assertEqual(len(bounds), 1)
        self.assertAlmostEqual(offsets.pop(), -7.5, delta=0.005)
        first_avg = first_block / 1000.0
        rest_avg = remaining / (self.ROUNDS - 1000.0)
        self.assertLess(rest_avg, first_avg * 3.0)


class TestOffsetFilter(unittest.TestCase):
    def test_empty_window_evaluates_to_none(self):
        self.assertIsNone(OffsetFilter().evaluate())

    def test_outliers_are_rejected(self):
        filt = OffsetFilter(window=16, select=8)
        for _ in range(15):
            filt.add(1.0, 0.04)
        filt.add(1801.0, 0.04)
        result = filt.evaluate()
        self.assertAlmostEqual(result.offset, 1.0, delta=1e-9)

    def test_spiky_samples_are_not_selected(self):
        filt = OffsetFilter(window=16, select=8)
        for _ in range(12):
            filt.add(1.0, 0.04)
        for _ in range(4):
            filt.add(1.5, 1.0)
        result = filt.evaluate()
        self.assertAlmostEqual(result.offset, 1.0, delta=1e-9)
        self.assertLess(result.confidence, 1.0)

    def test_bound_covers_truth_for_clean_samples(self):
        filt = OffsetFilter(window=16, select=8)
        truth = 3.25
        for noise, delay in [(0.01, 0.04), (-0.015, 0.05), (0.005, 0.04)] * 4:
            filt.add(truth + noise, delay)
        result = filt.evaluate()
        self.assertGreaterEqual(result.error_bound, abs(result.offset - truth))

    def test_reset_clears_the_window(self):
        filt = OffsetFilter(window=8, select=4)
        filt.add(1.0, 0.04)
        filt.reset()
        self.assertEqual(len(filt), 0)
        self.assertIsNone(filt.evaluate())

    def test_bad_geometry_is_rejected(self):
        with self.assertRaises(ValueError):
            OffsetFilter(window=4, select=8)
        with self.assertRaises(ValueError):
            OffsetFilter(select=0)


if __name__ == "__main__":
    unittest.main()
