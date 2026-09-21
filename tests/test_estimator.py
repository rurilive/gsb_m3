"""单发偏移探针口径的锁定测试。"""

import unittest

from steadyclock.estimator import OffsetProbe
from steadyclock.simclock import Link, Loopback, PeerClock
from steadyclock.source import ManualSource


def make_probe(true_offset=2.0, service=0.0005, **link_kwargs):
    source = ManualSource(wall=1000.0)
    peer = PeerClock(true_offset=true_offset)
    link = Link(seed=5, **link_kwargs)
    return OffsetProbe(Loopback(source, peer, link, service=service)), source


class TestOffsetProbe(unittest.TestCase):
    def test_probe_hands_back_a_float(self):
        probe, _source = make_probe()
        self.assertIsInstance(probe.probe(), float)

    def test_probe_lands_near_the_injected_offset(self):
        probe, _source = make_probe(true_offset=2.0, base_delay=0.02,
                                    jitter=0.004)
        for _ in range(20):
            value = probe.probe()
            self.assertGreater(value, 1.0)
            self.assertLess(value, 3.0)

    def test_probe_moves_with_the_injected_offset(self):
        probe, _source = make_probe(true_offset=-7.5, base_delay=0.02,
                                    jitter=0.004)
        for _ in range(20):
            value = probe.probe()
            self.assertGreater(value, -9.0)
            self.assertLess(value, -6.0)

    def test_probe_costs_at_least_one_round_trip(self):
        probe, source = make_probe(base_delay=0.01, jitter=0.0, service=0.001)
        before = source.monotonic()
        probe.probe()
        self.assertGreaterEqual(source.monotonic() - before, 0.021 - 1e-9)

    def test_probe_follows_a_peer_clock_recalibration(self):
        source = ManualSource(wall=1000.0)
        peer = PeerClock(true_offset=2.0)
        link = Link(base_delay=0.01, jitter=0.0, seed=9)
        probe = OffsetProbe(Loopback(source, peer, link, service=0.0))
        first = probe.probe()
        peer.true_offset = -3.0
        second = probe.probe()
        self.assertLess(second - first, -4.0)


if __name__ == "__main__":
    unittest.main()
