"""timeoutkit 线上问题的防回归测试。

对应五类曾在线上出现的现象：
1. 上游超时返回后，下游写操作仍在后台继续，冒出重复通知；
2. 父层预算更紧时，子层仍按自身更长的 timeout 跑满；
3. NTP 校时回拨/前拨墙钟，导致预算被拉长或提前掐断；
4. 拿到已取消（或已过期）的上下文仍能发起新调用；
5. 父级取消后，在途调用不能立刻中断。
"""
import threading
import time
import unittest

from timeoutkit import CallContext, Cancelled, FakeClock, Timeout, call
from timeoutkit.deadline import Deadline


class TestWallClockJump(unittest.TestCase):
    def test_deadline_ignores_wall_clock_backward_jump(self):
        clock = FakeClock(start=1000.0)
        deadline = Deadline(10.0, clock)
        clock.advance(9.0)
        self.assertGreater(deadline.remaining(), 0.0)
        clock.jump_wall(-500.0)  # 旧实现下墙钟回拨会让预算凭空多出 500 秒
        self.assertGreater(deadline.remaining(), 0.0)
        self.assertLess(deadline.remaining(), 2.0)
        clock.advance(1.5)
        self.assertTrue(deadline.expired())

    def test_deadline_ignores_wall_clock_forward_jump(self):
        clock = FakeClock(start=1000.0)
        deadline = Deadline(10.0, clock)
        clock.advance(1.0)
        clock.jump_wall(1000.0)  # 旧实现下墙钟前跳会让预算被提前掐断
        self.assertGreater(deadline.remaining(), 8.0)
        self.assertFalse(deadline.expired())

    def test_context_deadline_is_not_moved_by_jump_wall(self):
        clock = FakeClock(start=0.0)
        ctx = CallContext(clock=clock, timeout=10.0)
        clock.advance(2.0)
        clock.jump_wall(-3600.0)
        self.assertFalse(ctx.expired())
        clock.jump_wall(7200.0)
        self.assertFalse(ctx.expired())
        clock.advance(8.5)
        self.assertTrue(ctx.expired())


class TestChildBudgetClamp(unittest.TestCase):
    def test_child_timeout_is_clamped_to_parent_remaining(self):
        clock = FakeClock(start=100.0)
        parent = CallContext(clock=clock, timeout=0.8)
        kid = parent.child(timeout=5.0)  # 父只给 800ms，子自配 5s
        self.assertLess(kid.remaining(), 0.8 + 1e-9)
        self.assertGreater(kid.remaining(), 0.8 - 1e-6)

    def test_child_without_timeout_inherits_parent_deadline(self):
        clock = FakeClock(start=0.0)
        parent = CallContext(clock=clock, timeout=5.0)
        kid = parent.child()
        grandkid = kid.child()
        self.assertAlmostEqual(grandkid.remaining(), 5.0, places=6)
        clock.advance(5.5)
        self.assertTrue(kid.expired())
        self.assertTrue(grandkid.expired())

    def test_child_cannot_outlive_parent_in_real_time(self):
        parent = CallContext(timeout=0.3)
        kid = parent.child(timeout=5.0)

        def slow():
            time.sleep(2.0)

        started = time.monotonic()
        with self.assertRaises(Timeout):
            call(slow, ctx=kid)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 1.0)
        self.assertTrue(kid.cancelled)


class TestTimeoutCancelsInFlightWork(unittest.TestCase):
    def test_timed_out_context_stops_cooperative_downstream(self):
        ctx = CallContext(timeout=0.05)
        reached_sleep = threading.Event()
        stopped = threading.Event()
        written = []

        def write_with_duplicate_risk():
            try:
                ctx.check()
                reached_sleep.set()
                time.sleep(0.3)  # 不可中断的阻塞：超时在这里发生
                ctx.check()       # 醒来后必须发现自己已被取消
                written.append("通知")  # 不应再执行：否则就是重复通知
            except Cancelled:
                stopped.set()

        with self.assertRaises(Timeout):
            call(write_with_duplicate_risk, ctx=ctx)
        self.assertTrue(stopped.wait(1.0))
        self.assertEqual(written, [])
        self.assertTrue(ctx.cancelled)

    def test_timeout_cancels_children_as_well(self):
        root = CallContext(timeout=0.05)
        kid = root.child(timeout=10.0)
        with self.assertRaises(Timeout):
            call(lambda: time.sleep(0.3), ctx=root)
        self.assertTrue(root.cancelled)
        self.assertTrue(kid.cancelled)

    def test_implicit_child_timeout_does_not_cancel_parent(self):
        parent = CallContext(timeout=5.0)
        with self.assertRaises(Timeout):
            call(lambda: time.sleep(0.3), ctx=parent, timeout=0.05)
        self.assertFalse(parent.cancelled)
        self.assertEqual(call(lambda: "still usable", ctx=parent), "still usable")


class TestReuseAbortedContext(unittest.TestCase):
    def test_cancelled_context_rejects_new_call(self):
        ctx = CallContext(timeout=5.0)
        ctx.cancel()
        ran = []

        def must_not_run():
            ran.append(True)
            return "oops"

        with self.assertRaises(Cancelled):
            call(must_not_run, ctx=ctx)
        self.assertEqual(ran, [])

    def test_cancelled_child_rejects_new_call(self):
        parent = CallContext(timeout=5.0)
        kid = parent.child(timeout=1.0)
        parent.cancel()

        with self.assertRaises(Cancelled):
            call(lambda: "oops", ctx=kid)

    def test_expired_context_rejects_new_call(self):
        clock = FakeClock(start=0.0)
        ctx = CallContext(clock=clock, timeout=1.0)
        clock.advance(2.0)
        ran = []

        with self.assertRaises(Timeout):
            call(lambda: ran.append(True), ctx=ctx)
        self.assertEqual(ran, [])
        self.assertTrue(ctx.cancelled)


class TestCancellationDuringCall(unittest.TestCase):
    def test_parent_cancel_interrupts_in_flight_call(self):
        parent = CallContext()  # 无自身预算，只能被父级取消
        kid = parent.child()
        started = threading.Event()

        def long_running():
            started.set()
            time.sleep(5.0)

        def cancel_soon():
            started.wait(1.0)
            time.sleep(0.05)
            parent.cancel()

        threading.Thread(target=cancel_soon, daemon=True).start()
        begin = time.monotonic()
        with self.assertRaises(Cancelled):
            call(long_running, ctx=kid)
        self.assertLess(time.monotonic() - begin, 1.0)

    def test_check_raises_timeout_and_cancels_subtree(self):
        clock = FakeClock(start=0.0)
        root = CallContext(clock=clock, timeout=1.0)
        kid = root.child(timeout=5.0)
        clock.advance(2.0)
        with self.assertRaises(Timeout):
            root.check()
        self.assertTrue(root.cancelled)
        self.assertTrue(kid.cancelled)
        with self.assertRaises(Cancelled):
            kid.check()


if __name__ == "__main__":
    unittest.main()
