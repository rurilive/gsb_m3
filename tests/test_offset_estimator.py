"""OffsetEstimator 的验收测试：真值由 simclock 注入，估计要对拍得上。

覆盖：干净链路与不对称链路的收敛、延迟尖峰与错误样本下的稳健、
墙钟回拨与前跳期间超时与估计纹丝不动、上万轮采样后不漂、误差界
不涨、单轮耗时不涨。
"""

import time
import unittest

from steadyclock import (
    Deadline,
    Estimate,
    Link,
    Loopback,
    ManualSource,
    OffsetEstimator,
    PeerClock,
    Stopwatch,
)

WARMUP = 200


def make_estimator(true_offset=2.0, service=0.0005, window=64, **link_kwargs):
    source = ManualSource(wall=1000.0)
    peer = PeerClock(true_offset=true_offset)
    link = Link(seed=42, **link_kwargs)
    loopback = Loopback(source, peer, link, service=service)
    return OffsetEstimator(loopback, window=window), source, link


class TestConvergence(unittest.TestCase):
    def test_converges_into_tolerance_on_a_clean_link(self):
        estimator, _source, _link = make_estimator(
            true_offset=2.0, base_delay=0.02, jitter=0.004)
        estimate = None
        for _ in range(40):
            estimate = estimator.sample()
        self.assertAlmostEqual(estimate.offset, 2.0, delta=0.005)

    def test_converges_on_an_asymmetric_link(self):
        estimator, _source, _link = make_estimator(
            true_offset=-7.5, base_delay=0.02, jitter=0.004, skew=0.004)
        estimate = None
        for _ in range(60):
            estimate = estimator.sample()
        # 不对称带来至多 skew/2 的固有偏差，容差放宽到它之外一点
        self.assertAlmostEqual(estimate.offset, -7.5, delta=0.005)

    def test_sample_hands_back_an_estimate(self):
        estimator, _source, _link = make_estimator(
            base_delay=0.02, jitter=0.004)
        estimate = estimator.sample()
        self.assertIsInstance(estimate, Estimate)
        self.assertIsInstance(estimate.offset, float)
        self.assertIsInstance(estimate.error_bound, float)
        self.assertIsInstance(estimate.confidence, float)
        self.assertGreater(estimate.error_bound, 0.0)
        self.assertGreaterEqual(estimate.confidence, 0.0)
        self.assertLessEqual(estimate.confidence, 1.0)


class TestRobustness(unittest.TestCase):
    def test_spikes_and_faults_do_not_pull_the_estimate(self):
        estimator, _source, link = make_estimator(
            true_offset=2.0, base_delay=0.02, jitter=0.004, skew=0.004,
            spike_chance=0.1, spike_factor=25.0,
            fault_chance=0.15, fault_shift=1800.0)
        estimate = None
        for _ in range(WARMUP + 200):
            estimate = estimator.sample()
        self.assertGreater(link.spikes, 0)
        self.assertGreater(link.faults, 0)
        self.assertAlmostEqual(estimate.offset, 2.0, delta=0.005)

    def test_error_bound_contains_the_truth(self):
        estimator, _source, _link = make_estimator(
            true_offset=2.0, base_delay=0.02, jitter=0.004, skew=0.004,
            spike_chance=0.1, fault_chance=0.15)
        for _ in range(WARMUP):
            estimator.sample()
        for _ in range(500):
            estimate = estimator.sample()
            self.assertLessEqual(
                abs(estimate.offset - 2.0), estimate.error_bound)

    def test_confidence_drops_on_a_dirty_link(self):
        clean, _s1, _l1 = make_estimator(base_delay=0.02, jitter=0.004)
        dirty, _s2, _l2 = make_estimator(
            base_delay=0.02, jitter=0.004, spike_chance=0.1,
            fault_chance=0.15)
        clean_estimate = dirty_estimate = None
        for _ in range(WARMUP):
            clean_estimate = clean.sample()
            dirty_estimate = dirty.sample()
        self.assertGreater(clean_estimate.confidence, 0.95)
        self.assertLess(dirty_estimate.confidence,
                        clean_estimate.confidence)

    def test_converged_estimate_does_not_jitter(self):
        estimator, _source, _link = make_estimator(
            true_offset=2.0, base_delay=0.02, jitter=0.004, skew=0.004,
            spike_chance=0.1, fault_chance=0.15)
        for _ in range(WARMUP):
            estimator.sample()
        offsets = [estimator.sample().offset for _ in range(1000)]
        self.assertLess(max(offsets) - min(offsets), 0.002)


class TestWallClockImmunity(unittest.TestCase):
    def test_deadline_and_stopwatch_ignore_wall_steps(self):
        source = ManualSource(wall=1000.0)
        deadline = Deadline(source, 5.0)
        watch = Stopwatch(source)
        source.sleep(2.0)
        for _ in range(10):
            source.step_wall(-300.0)
            source.step_wall(250.0)
        self.assertAlmostEqual(deadline.elapsed(), 2.0)
        self.assertAlmostEqual(deadline.remaining(), 3.0)
        self.assertFalse(deadline.expired())
        self.assertAlmostEqual(watch.elapsed(), 2.0)

    def test_estimator_ignores_wall_steps(self):
        stepped, stepped_source, _l1 = make_estimator(
            true_offset=2.0, base_delay=0.02, jitter=0.004, skew=0.004,
            spike_chance=0.1, fault_chance=0.15)
        calm, _s2, _l2 = make_estimator(
            true_offset=2.0, base_delay=0.02, jitter=0.004, skew=0.004,
            spike_chance=0.1, fault_chance=0.15)
        for round_no in range(400):
            stepped_estimate = stepped.sample()
            calm_estimate = calm.sample()
            if round_no % 3 == 0:
                stepped_source.step_wall(-300.0)
            else:
                stepped_source.step_wall(120.0)
            self.assertEqual(stepped_estimate, calm_estimate)


class TestLongRun(unittest.TestCase):
    def test_ten_thousand_rounds_stay_put(self):
        estimator, _source, _link = make_estimator(
            true_offset=2.0, base_delay=0.02, jitter=0.004, skew=0.004,
            spike_chance=0.1, fault_chance=0.15)
        for _ in range(WARMUP):
            estimator.sample()
        first = estimator.sample()
        early_cost = self._time_rounds(estimator, 1000)
        midpoint = estimator.sample()
        for _ in range(8000):
            estimator.sample()
        last = estimator.sample()
        late_cost = self._time_rounds(estimator, 1000)

        self.assertAlmostEqual(last.offset, 2.0, delta=0.005)
        self.assertAlmostEqual(last.offset, first.offset, delta=0.002)
        self.assertAlmostEqual(midpoint.offset, first.offset, delta=0.002)
        self.assertLessEqual(last.error_bound, first.error_bound + 0.002)
        self.assertLessEqual(abs(last.offset - 2.0), last.error_bound)
        self.assertLess(late_cost, early_cost * 3 + 0.05)

    @staticmethod
    def _time_rounds(estimator, rounds):
        start = time.perf_counter()
        for _ in range(rounds):
            estimator.sample()
        return time.perf_counter() - start


if __name__ == "__main__":
    unittest.main()
