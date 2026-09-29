"""ListTimer 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from wheelish.timer import ListTimer


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class TestListTimer(unittest.TestCase):
    def test_register_and_fire(self):
        c = FakeClock()
        t = ListTimer(clock=c)
        t.register(5, payload="a")
        t.register(10, payload="b")
        due = t.tick(5)
        self.assertEqual([h.payload for h in due], ["a"])
        self.assertEqual(t.size, 1)
        due = t.tick(10)
        self.assertEqual([h.payload for h in due], ["b"])

    def test_nothing_due(self):
        c = FakeClock()
        t = ListTimer(clock=c)
        t.register(10, payload="x")
        self.assertEqual(t.tick(9), [])
        self.assertEqual(t.size, 1)

    def test_cancel_prevents_fire(self):
        c = FakeClock()
        t = ListTimer(clock=c)
        h = t.register(5, payload="x")
        self.assertTrue(h.cancel())
        self.assertEqual(t.tick(5), [])
        self.assertTrue(h.cancelled)

    def test_double_cancel_returns_false(self):
        c = FakeClock()
        t = ListTimer(clock=c)
        h = t.register(5, payload="x")
        self.assertTrue(h.cancel())
        self.assertFalse(h.cancel())

    def test_deadline_equal_to_now_fires(self):
        c = FakeClock()
        t = ListTimer(clock=c)
        t.register(5, payload="x")
        due = t.tick(5)
        self.assertEqual(len(due), 1)

    def test_backwards_clock_rejected(self):
        c = FakeClock()
        t = ListTimer(clock=c)
        with self.assertRaises(ValueError):
            t.tick(-1)

    def test_nonpositive_delay_rejected(self):
        c = FakeClock()
        t = ListTimer(clock=c)
        with self.assertRaises(ValueError):
            t.register(0)
        with self.assertRaises(ValueError):
            t.register(-3)


if __name__ == "__main__":
    unittest.main()