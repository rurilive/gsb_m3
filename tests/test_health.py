"""常驻自检测试：注入假时钟定周期节奏，threading.Event 控制探针卡/放。"""

import threading
import time
import unittest

from healthd.monitor import DEGRADED, DOWN, OK, HealthMonitor


def wait_for(pred, timeout=5.0, step=0.005):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return
        time.sleep(step)
    raise AssertionError("condition not met in time")


class FakeClock:
    """可控时钟：time()/event() 与检查线程协同，advance() 推动下一轮。"""

    def __init__(self, start=1000.0):
        self._now = start
        self._cond = threading.Condition()

    def time(self):
        with self._cond:
            return self._now

    def sleep(self, seconds):
        with self._cond:
            deadline = self._now + seconds
            while self._now < deadline:
                self._cond.wait(None)

    def advance(self, seconds):
        with self._cond:
            self._now += seconds
            self._cond.notify_all()

    def event(self):
        return _FakeEvent(self)


class _FakeEvent:
    """与 FakeClock 共享条件变量：set() 或 advance() 都能唤醒 wait。"""

    def __init__(self, clock):
        self._clock = clock
        self._cond = clock._cond
        self._set = False

    def is_set(self):
        with self._cond:
            return self._set

    def set(self):
        with self._cond:
            self._set = True
            self._cond.notify_all()

    def clear(self):
        with self._cond:
            self._set = False

    def wait(self, timeout=None):
        with self._cond:
            if timeout is None:
                while not self._set:
                    self._cond.wait()
                return True
        with self._cond:
            deadline = self._clock.time() + timeout
            while not self._set and self._clock.time() < deadline:
                self._cond.wait(max(0.0, deadline - self._clock.time()))
            return self._set


def make_recorder():
    flips = []

    def fn(old, new):
        flips.append((old, new))

    return fn, flips


class TestResidentHealth(unittest.TestCase):
    def test_initial_state_is_down_and_not_ready(self):
        clock = FakeClock()
        mon = HealthMonitor(period=10.0, clock=clock)
        mon.register("a", lambda: "")
        self.assertEqual(mon.status(), DOWN)
        self.assertFalse(mon.ready())

    def test_timeout_degrades_then_recovers(self):
        clock = FakeClock()
        mon = HealthMonitor(period=10.0, k=2, clock=clock)
        hang = threading.Event()
        flips = []
        flipped = threading.Event()

        def on_flip(old, new):
            flips.append((old, new))
            flipped.set()

        mon.on_change(on_flip)
        mon.register("db", lambda: "primary", timeout=1.0)
        mon.register("queue", lambda: hang.wait() or "drained", timeout=0.15)
        mon.register("disk", lambda: "72%", timeout=1.0)

        mon.start()
        self.assertTrue(flipped.wait(3.0))
        self.assertEqual(flips, [(DOWN, DEGRADED)])
        snap = mon.snapshot()
        self.assertTrue(snap["db"].ok)
        self.assertFalse(snap["queue"].ok)
        self.assertIn("timeout", snap["queue"].detail)
        self.assertTrue(snap["disk"].ok)
        self.assertEqual(mon.status(), DEGRADED)
        self.assertTrue(mon.ready())

        hang.set()
        flipped.clear()
        clock.advance(10.0)
        self.assertTrue(flipped.wait(3.0))
        self.assertEqual(flips[-1], (DEGRADED, OK))
        self.assertEqual(mon.status(), OK)
        self.assertTrue(mon.ready())
        self.assertTrue(mon.snapshot()["queue"].ok)

        mon.stop()
        self.assertFalse(mon.running)

    def test_kn_threshold_flips(self):
        clock = FakeClock()
        mon = HealthMonitor(period=10.0, k=2, clock=clock)
        broken = {"a": False, "b": False, "c": False}

        def probe(name):
            def _fn():
                if broken[name]:
                    raise RuntimeError(f"{name} down")
                return f"{name} ok"

            return _fn

        for name in ("a", "b", "c"):
            mon.register(name, probe(name), timeout=1.0)

        recorder, flips = make_recorder()
        mon.on_change(recorder)
        mon.start()
        wait_for(lambda: mon.status() == OK)
        self.assertTrue(mon.ready())

        broken["c"] = True
        clock.advance(10.0)
        wait_for(lambda: mon.status() == DEGRADED)
        self.assertTrue(mon.ready())

        broken["b"] = True
        clock.advance(10.0)
        wait_for(lambda: mon.status() == DOWN)
        self.assertFalse(mon.ready())

        broken["c"] = False
        clock.advance(10.0)
        wait_for(lambda: mon.status() == DEGRADED)
        self.assertTrue(mon.ready())

        broken["b"] = False
        clock.advance(10.0)
        wait_for(lambda: mon.status() == OK)
        self.assertTrue(mon.ready())

        self.assertEqual(
            flips,
            [(DOWN, OK), (OK, DEGRADED), (DEGRADED, DOWN),
             (DOWN, DEGRADED), (DEGRADED, OK)],
        )
        mon.stop()

    def test_default_k_requires_all(self):
        clock = FakeClock()
        mon = HealthMonitor(period=10.0, clock=clock)
        broken = threading.Event()
        mon.register("a", lambda: "" if not broken.is_set() else (_ for _ in ()).throw(RuntimeError("x")))
        mon.register("b", lambda: "")
        mon.start()
        wait_for(lambda: mon.status() == OK)

        broken.set()
        clock.advance(10.0)
        wait_for(lambda: mon.status() == DOWN)
        self.assertFalse(mon.ready())
        mon.stop()

    def test_callback_exception_does_not_stop_checks(self):
        clock = FakeClock()
        mon = HealthMonitor(period=10.0, k=1, clock=clock)
        broken = threading.Event()
        flips = []
        flipped = threading.Event()

        def noisy(old, new):
            raise RuntimeError("listener boom")

        def quiet(old, new):
            flips.append((old, new))
            flipped.set()

        mon.on_change(noisy)
        mon.on_change(quiet)
        mon.register("a", lambda: "" if not broken.is_set() else (_ for _ in ()).throw(RuntimeError("x")))
        mon.register("b", lambda: "")
        mon.start()
        self.assertTrue(flipped.wait(3.0))
        self.assertEqual(flips[-1], (DOWN, OK))

        flipped.clear()
        broken.set()
        clock.advance(10.0)
        self.assertTrue(flipped.wait(3.0))
        self.assertEqual(flips[-1], (OK, DEGRADED))
        self.assertTrue(mon.running)
        mon.stop()

    def test_callback_runs_on_check_thread(self):
        clock = FakeClock()
        mon = HealthMonitor(period=10.0, clock=clock)
        seen = []
        done = threading.Event()
        mon.on_change(lambda old, new: seen.append(threading.current_thread().name) or done.set())
        mon.register("a", lambda: "")
        mon.start()
        self.assertTrue(done.wait(3.0))
        self.assertEqual(seen, ["healthd-monitor"])
        mon.stop()

    def test_injected_clock_paces_periods(self):
        clock = FakeClock()
        counts = {"n": 0}

        def probe():
            counts["n"] += 1
            return ""

        mon = HealthMonitor(period=10.0, jitter=0.0, clock=clock)
        mon.register("a", probe)
        mon.start()
        wait_for(lambda: counts["n"] == 1)
        clock.advance(10.0)
        wait_for(lambda: counts["n"] == 2)
        clock.advance(10.0)
        wait_for(lambda: counts["n"] == 3)
        mon.stop()

    def test_stop_interrupts_clock_wait(self):
        clock = FakeClock()
        mon = HealthMonitor(period=1000.0, clock=clock)
        mon.register("a", lambda: "")
        mon.start()
        wait_for(lambda: mon.status() == OK)
        start = time.monotonic()
        mon.stop()
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertFalse(mon.running)

    def test_snapshot_concurrent_with_checks(self):
        clock = FakeClock()
        mon = HealthMonitor(period=10.0, clock=clock)
        mon.register("a", lambda: "")
        mon.register("b", lambda: "ok")
        mon.start()
        wait_for(lambda: mon.status() == OK)

        errors = []
        stop_readers = threading.Event()

        def reader():
            while not stop_readers.is_set():
                try:
                    snap = mon.snapshot()
                    _ = mon.status()
                    _ = mon.ready()
                    _ = mon.quorum()
                    for result in snap.values():
                        _ = result.ok
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for _ in range(5):
            clock.advance(10.0)
            time.sleep(0.02)
        mon.stop()
        stop_readers.set()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_jitter_bounds(self):
        seen = []

        def rng(lo, hi):
            seen.append((lo, hi))
            return hi

        mon = HealthMonitor(period=5.0, jitter=0.5, clock=FakeClock(), rng=rng)
        self.assertEqual(mon._next_delay(), 5.5)
        self.assertEqual(seen[-1], (4.5, 5.5))

        mon0 = HealthMonitor(period=5.0, jitter=0.0, clock=FakeClock())
        self.assertEqual(mon0._next_delay(), 5.0)

    def test_slow_probe_without_timeout_passes(self):
        clock = FakeClock()
        mon = HealthMonitor(period=10.0, clock=clock)
        mon.register("slow", lambda: time.sleep(0.15) or "done")
        mon.start()
        wait_for(lambda: mon.status() == OK)
        self.assertEqual(mon.snapshot()["slow"].detail, "done")
        mon.stop()

    def test_start_twice_and_repeat_stop(self):
        mon = HealthMonitor(clock=FakeClock())
        mon.register("a", lambda: "")
        mon.start()
        with self.assertRaises(RuntimeError):
            mon.start()
        mon.stop()
        mon.stop()
        self.assertFalse(mon.running)

    def test_invalid_arguments(self):
        with self.assertRaises(ValueError):
            HealthMonitor(period=0)
        with self.assertRaises(ValueError):
            HealthMonitor(period=1.0, jitter=2.0)
        mon = HealthMonitor(clock=FakeClock())
        with self.assertRaises(ValueError):
            mon.register("a", lambda: "", timeout=0)

    def test_manual_run_once_still_works(self):
        mon = HealthMonitor(clock=FakeClock())
        mon.register("a", lambda: "x")
        snap = mon.run_once()
        self.assertTrue(snap["a"].ok)
        self.assertEqual(snap["a"].detail, "x")


if __name__ == "__main__":
    unittest.main()
