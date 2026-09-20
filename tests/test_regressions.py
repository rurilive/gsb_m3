"""线上事故回归测试：单调钟、预算沿父链取紧、取消唤醒、取消后拒发新调用。"""
import threading
import time
import unittest

from timeoutkit import CallContext, Cancelled, FakeClock, Timeout, call


class TestMonotonicDeadline(unittest.TestCase):
    """Deadline 必须基于单调钟：墙钟被校时拨动不应影响预算。"""

    def test_wall_jump_backward_does_not_stall(self):
        clock = FakeClock(start=100.0)
        ctx = CallContext(clock=clock, timeout=5.0)
        clock.jump_wall(-30.0)
        self.assertFalse(ctx.expired())
        self.assertAlmostEqual(ctx.remaining(), 5.0, places=6)
        clock.advance(5.0)
        self.assertTrue(ctx.expired())

    def test_wall_jump_forward_does_not_expire_early(self):
        clock = FakeClock(start=100.0)
        ctx = CallContext(clock=clock, timeout=5.0)
        clock.jump_wall(3600.0)
        self.assertFalse(ctx.expired())
        self.assertAlmostEqual(ctx.remaining(), 5.0, places=6)


class TestBudgetInheritance(unittest.TestCase):
    """子上下文的可用预算不能超过父级剩余预算。"""

    def test_child_budget_capped_by_parent(self):
        clock = FakeClock(start=0.0)
        parent = CallContext(clock=clock, timeout=0.8)
        kid = parent.child(timeout=5.0)
        self.assertAlmostEqual(kid.remaining(), 0.8, places=6)

    def test_child_expires_with_parent(self):
        clock = FakeClock(start=0.0)
        parent = CallContext(clock=clock, timeout=0.8)
        kid = parent.child(timeout=5.0)
        clock.advance(1.0)
        self.assertTrue(kid.expired())

    def test_call_under_parent_budget_times_out_on_parent(self):
        parent = CallContext(timeout=0.1)
        kid = parent.child(timeout=5.0)
        with self.assertRaises(Timeout):
            call(lambda: time.sleep(1.0), ctx=kid)


class TestCancelWakesCaller(unittest.TestCase):
    """等待中的 call 必须在取消后尽快退出，而不是干等到预算耗尽。"""

    def test_cancel_during_call_raises_cancelled_promptly(self):
        ctx = CallContext(timeout=30.0)
        started = time.monotonic()

        def cancel_soon():
            time.sleep(0.05)
            ctx.cancel()

        threading.Thread(target=cancel_soon).start()
        with self.assertRaises(Cancelled):
            call(lambda: time.sleep(5.0), ctx=ctx)
        self.assertLess(time.monotonic() - started, 2.0)

    def test_cancel_wakes_call_without_deadline(self):
        ctx = CallContext()
        threading.Timer(0.05, ctx.cancel).start()
        with self.assertRaises(Cancelled):
            call(lambda: time.sleep(5.0), ctx=ctx)


class TestCancelledContextRejectsNewCalls(unittest.TestCase):
    """已取消的上下文不得再发起新调用。"""

    def test_call_on_cancelled_context_raises_without_running(self):
        ctx = CallContext(timeout=5.0)
        ctx.cancel()
        ran = []
        with self.assertRaises(Cancelled):
            call(lambda: ran.append(True), ctx=ctx)
        self.assertEqual(ran, [])

    def test_child_call_on_cancelled_parent_rejected(self):
        root = CallContext(timeout=5.0)
        kid = root.child(timeout=1.0)
        root.cancel()
        ran = []
        with self.assertRaises(Cancelled):
            call(lambda: ran.append(True), ctx=kid)
        self.assertEqual(ran, [])

    def test_check_sees_parent_cancellation(self):
        root = CallContext(timeout=5.0)
        kid = root.child(timeout=1.0)
        root.cancel()
        with self.assertRaises(Cancelled):
            kid.check()


if __name__ == "__main__":
    unittest.main()
