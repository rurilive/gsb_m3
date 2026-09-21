"""四处线上问题的回归测试：饥饿、同级乱序、撤单、超时边界。"""

import unittest

from fairlease.lease import FairLease


class FakeClock:
    def __init__(self, t=0.0):
        self.now = float(t)

    def __call__(self):
        return self.now


class TestStarvation(unittest.TestCase):
    def test_aged_low_priority_eventually_granted(self):
        clock = FakeClock(0.0)
        fl = FairLease(clock=clock, aging=5.0)
        fl.request("batch", 9)
        served = []
        for t in range(1, 7):
            clock.now = float(t)
            fl.request(f"hot{t}", 0)
            served.append(fl.grant())
        self.assertEqual(served[4], "batch")
        self.assertIn("batch", served)

    def test_aged_requests_served_fifo(self):
        clock = FakeClock(0.0)
        fl = FairLease(clock=clock, aging=5.0)
        fl.request("low1", 9)
        clock.now = 1.0
        fl.request("low2", 8)
        clock.now = 10.0
        fl.request("hot", 0)
        self.assertEqual([fl.grant(), fl.grant(), fl.grant()],
                         ["low1", "low2", "hot"])

    def test_unaged_high_priority_still_first(self):
        clock = FakeClock(0.0)
        fl = FairLease(clock=clock, aging=5.0)
        fl.request("low", 9)
        clock.now = 2.0  # 还没等够 aging
        fl.request("hot", 0)
        self.assertEqual(fl.grant(), "hot")


class TestSamePriorityFifo(unittest.TestCase):
    def test_same_priority_granted_in_arrival_order(self):
        fl = FairLease(clock=FakeClock(0.0), aging=5.0)
        fl.request("zeta", 2)
        fl.request("alpha", 2)
        fl.request("mid", 2)
        self.assertEqual([fl.grant(), fl.grant(), fl.grant()],
                         ["zeta", "alpha", "mid"])

    def test_pending_same_priority_fifo(self):
        fl = FairLease(clock=FakeClock(0.0), aging=5.0)
        fl.request("zeta", 2)
        fl.request("alpha", 2)
        self.assertEqual(fl.pending(), ["zeta", "alpha"])


class TestCancel(unittest.TestCase):
    def test_cancelled_request_leaves_pending(self):
        fl = FairLease(clock=FakeClock(0.0), aging=5.0)
        doomed = fl.request("ghost", 0)
        fl.request("real", 5)
        self.assertTrue(fl.cancel(doomed))
        self.assertEqual(fl.pending(), ["real"])

    def test_cancelled_request_not_granted(self):
        fl = FairLease(clock=FakeClock(0.0), aging=5.0)
        doomed = fl.request("ghost", 0)
        fl.request("real", 5)
        fl.cancel(doomed)
        self.assertEqual(fl.grant(), "real")
        self.assertIsNone(fl.grant())

    def test_cancel_twice_returns_false(self):
        fl = FairLease(clock=FakeClock(0.0), aging=5.0)
        ticket = fl.request("a", 1)
        self.assertTrue(fl.cancel(ticket))
        self.assertFalse(fl.cancel(ticket))


class TestTimeoutBoundary(unittest.TestCase):
    def test_exactly_at_timeout_still_valid(self):
        clock = FakeClock(0.0)
        fl = FairLease(clock=clock, aging=5.0)
        fl.request("edge", 1, timeout=2.0)
        clock.now = 2.0
        self.assertEqual(fl.grant(), "edge")

    def test_beyond_timeout_dropped(self):
        clock = FakeClock(0.0)
        fl = FairLease(clock=clock, aging=5.0)
        fl.request("late", 1, timeout=2.0)
        clock.now = 2.5
        self.assertIsNone(fl.grant())
        self.assertEqual(fl.pending(), [])


if __name__ == "__main__":
    unittest.main()
