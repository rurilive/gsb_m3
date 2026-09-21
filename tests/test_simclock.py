"""对端时钟与往返链路的锁定测试。"""

import unittest

from steadyclock.simclock import Link, Loopback, PeerClock
from steadyclock.source import ManualSource


class TestPeerClock(unittest.TestCase):
    def test_fixed_offset_shifts_the_whole_axis(self):
        peer = PeerClock(true_offset=3.0)
        self.assertAlmostEqual(peer.wall_at(100.0), 103.0)
        self.assertAlmostEqual(peer.wall_at(0.0), 3.0)

    def test_drift_grows_with_local_time(self):
        peer = PeerClock(true_offset=3.0, drift=0.001)
        near = peer.wall_at(100.0)
        far = peer.wall_at(200.0)
        self.assertAlmostEqual(far - near, 100.1)


class TestLink(unittest.TestCase):
    def test_delays_stay_between_base_and_base_plus_jitter(self):
        link = Link(base_delay=0.01, jitter=0.002, seed=7)
        for _ in range(50):
            request, response, fault = link.plan()
            self.assertGreaterEqual(request, 0.01)
            self.assertLessEqual(request, 0.012)
            self.assertGreaterEqual(response, 0.01)
            self.assertLessEqual(response, 0.012)
            self.assertEqual(fault, 0.0)

    def test_skew_lands_on_the_response_leg(self):
        link = Link(base_delay=0.01, jitter=0.0, skew=0.02, seed=1)
        request, response, _fault = link.plan()
        self.assertAlmostEqual(request, 0.01)
        self.assertAlmostEqual(response, 0.03)

    def test_same_seed_replays_the_same_draws(self):
        first = Link(base_delay=0.01, spike_chance=0.3, seed=3)
        second = Link(base_delay=0.01, spike_chance=0.3, seed=3)
        self.assertEqual([first.plan() for _ in range(20)],
                         [second.plan() for _ in range(20)])

    def test_spikes_and_faults_show_up_and_are_counted(self):
        link = Link(base_delay=0.01, jitter=0.0, spike_chance=0.25,
                    spike_factor=10.0, fault_chance=0.25, seed=5)
        for _ in range(400):
            link.plan()
        self.assertGreater(link.spikes, 20)
        self.assertLess(link.spikes, 200)
        self.assertGreater(link.faults, 20)
        self.assertLess(link.faults, 200)


class TestLoopback(unittest.TestCase):
    def setUp(self):
        self.source = ManualSource(wall=1000.0)
        self.peer = PeerClock(true_offset=2.0)

    def test_exchange_consumes_one_round_trip(self):
        link = Link(base_delay=0.01, jitter=0.0, seed=11)
        loopback = Loopback(self.source, self.peer, link, service=0.001)
        before = self.source.monotonic()
        loopback.exchange()
        self.assertAlmostEqual(self.source.monotonic() - before, 0.021)

    def test_peer_stamps_span_the_service_time(self):
        link = Link(base_delay=0.01, jitter=0.0, seed=12)
        loopback = Loopback(self.source, self.peer, link, service=0.001)
        _t0, t1, t2, _t3 = loopback.exchange()
        self.assertAlmostEqual(t2 - t1, 0.001)

    def test_peer_stamps_carry_the_true_offset(self):
        link = Link(base_delay=0.01, jitter=0.0, seed=13)
        loopback = Loopback(self.source, self.peer, link, service=0.0)
        before = self.source.monotonic()
        _t0, t1, _t2, _t3 = loopback.exchange()
        self.assertAlmostEqual(t1 - before, 0.01 + 2.0)

    def test_fault_moves_both_peer_stamps_together(self):
        link = Link(base_delay=0.01, jitter=0.0, fault_chance=1.0,
                    fault_shift=1800.0, seed=14)
        loopback = Loopback(self.source, self.peer, link, service=0.0)
        before = self.source.monotonic()
        _t0, t1, _t2, _t3 = loopback.exchange()
        self.assertAlmostEqual(t1 - before, 0.01 + 2.0 + 1800.0)
        self.assertEqual(link.faults, 1)


if __name__ == "__main__":
    unittest.main()
