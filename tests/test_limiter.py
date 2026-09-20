"""FixedWindowLimiter 行为基线：单进程固定窗口语义。"""
import threading
import unittest

from quota import FixedWindowLimiter


class FakeClock:
    """手动推进的假时钟，避免测试真实 sleep。"""

    def __init__(self, now=1000.0):
        self.now = float(now)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestFixedWindowLimiter(unittest.TestCase):
    def test_allows_up_to_limit(self):
        lim = FixedWindowLimiter(limit=3, window=1.0, clock=FakeClock())
        self.assertEqual([lim.allow() for _ in range(3)], [True, True, True])

    def test_rejects_beyond_limit(self):
        lim = FixedWindowLimiter(limit=2, window=1.0, clock=FakeClock())
        self.assertTrue(lim.allow())
        self.assertTrue(lim.allow())
        self.assertFalse(lim.allow())

    def test_window_rollover_resets_count(self):
        clock = FakeClock(1000.0)
        lim = FixedWindowLimiter(limit=1, window=1.0, clock=clock)
        self.assertTrue(lim.allow())
        self.assertFalse(lim.allow())
        clock.advance(1.0)
        self.assertTrue(lim.allow())

    def test_windows_align_to_clock_grid(self):
        clock = FakeClock(1000.2)
        lim = FixedWindowLimiter(limit=1, window=1.0, clock=clock)
        self.assertTrue(lim.allow())
        clock.advance(0.5)
        self.assertFalse(lim.allow())
        clock.advance(0.4)
        self.assertTrue(lim.allow())

    def test_keys_are_isolated(self):
        lim = FixedWindowLimiter(limit=1, window=1.0, clock=FakeClock())
        self.assertTrue(lim.allow("a"))
        self.assertTrue(lim.allow("b"))
        self.assertFalse(lim.allow("a"))

    def test_remaining_tracks_usage(self):
        lim = FixedWindowLimiter(limit=3, window=1.0, clock=FakeClock())
        self.assertEqual(lim.remaining(), 3)
        lim.allow()
        lim.allow()
        self.assertEqual(lim.remaining(), 1)

    def test_remaining_never_negative(self):
        lim = FixedWindowLimiter(limit=1, window=1.0, clock=FakeClock())
        lim.allow()
        lim.allow()
        self.assertEqual(lim.remaining(), 0)

    def test_remaining_resets_next_window(self):
        clock = FakeClock(1000.0)
        lim = FixedWindowLimiter(limit=2, window=1.0, clock=clock)
        lim.allow()
        lim.allow()
        self.assertEqual(lim.remaining(), 0)
        clock.advance(1.0)
        self.assertEqual(lim.remaining(), 2)

    def test_rejects_invalid_args(self):
        with self.assertRaises(ValueError):
            FixedWindowLimiter(limit=0)
        with self.assertRaises(ValueError):
            FixedWindowLimiter(limit=1, window=0)

    def test_concurrent_allow_never_exceeds_limit(self):
        lim = FixedWindowLimiter(limit=50, window=60.0, clock=lambda: 1000.0)
        granted = []
        lock = threading.Lock()

        def worker():
            for _ in range(20):
                ok = lim.allow()
                with lock:
                    granted.append(ok)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(granted.count(True), 50)


if __name__ == "__main__":
    unittest.main()
