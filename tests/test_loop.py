"""LoopTimer 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from timectl.timer import LoopTimer


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class TestLoopTimer(unittest.TestCase):
    def test_register_and_fire(self):
        c = FakeClock()
        t = LoopTimer(clock=c)
        seen = []
        t.register(5, lambda: seen.append("a"))
        t.register(10, lambda: seen.append("b"))
        due = t.tick(5)
        self.assertEqual(seen, ["a"])
        self.assertEqual(len(due), 1)
        self.assertEqual(t.size, 1)
        t.tick(10)
        self.assertEqual(seen, ["a", "b"])

    def test_callback_called_synchronously(self):
        c = FakeClock()
        t = LoopTimer(clock=c)
        order = []
        t.register(5, lambda: order.append("cb"))
        order.append("before")
        t.tick(5)
        order.append("after")
        self.assertEqual(order, ["before", "cb", "after"])

    def test_nothing_due(self):
        c = FakeClock()
        t = LoopTimer(clock=c)
        seen = []
        t.register(10, lambda: seen.append("x"))
        self.assertEqual(t.tick(9), [])
        self.assertEqual(seen, [])
        self.assertEqual(t.size, 1)

    def test_cancel_prevents_fire(self):
        c = FakeClock()
        t = LoopTimer(clock=c)
        seen = []
        h = t.register(5, lambda: seen.append("x"))
        self.assertTrue(h.cancel())
        self.assertEqual(t.tick(5), [])
        self.assertEqual(seen, [])
        self.assertTrue(h.cancelled)

    def test_double_cancel_returns_false(self):
        c = FakeClock()
        t = LoopTimer(clock=c)
        h = t.register(5, lambda: None)
        self.assertTrue(h.cancel())
        self.assertFalse(h.cancel())

    def test_deadline_equal_to_now_fires(self):
        c = FakeClock()
        t = LoopTimer(clock=c)
        seen = []
        t.register(5, lambda: seen.append("x"))
        due = t.tick(5)
        self.assertEqual(len(due), 1)
        self.assertEqual(seen, ["x"])

    def test_fires_once_only(self):
        c = FakeClock()
        t = LoopTimer(clock=c)
        seen = []
        t.register(5, lambda: seen.append("x"))
        t.tick(5)
        t.tick(100)
        self.assertEqual(seen, ["x"])

    def test_backwards_clock_rejected(self):
        c = FakeClock()
        t = LoopTimer(clock=c)
        with self.assertRaises(ValueError):
            t.tick(-1)

    def test_nonpositive_delay_rejected(self):
        c = FakeClock()
        t = LoopTimer(clock=c)
        with self.assertRaises(ValueError):
            t.register(0, lambda: None)
        with self.assertRaises(ValueError):
            t.register(-3, lambda: None)


if __name__ == "__main__":
    unittest.main()
