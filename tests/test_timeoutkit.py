"""timeoutkit 公开行为基线：正常调用、预算内完成、单项超时、取消传播。

这些用例锁的是现有的对外契约，改动实现后必须原样全绿。
"""
import time
import unittest

from timeoutkit import CallContext, Cancelled, FakeClock, Timeout, call


class TestCall(unittest.TestCase):
    def test_returns_value(self):
        self.assertEqual(call(lambda: 7), 7)

    def test_propagates_exception(self):
        def boom():
            raise ValueError("下游失败")

        with self.assertRaises(ValueError):
            call(boom)

    def test_finishes_within_budget(self):
        ctx = CallContext(timeout=1.0)
        self.assertEqual(call(lambda: "ok", ctx=ctx), "ok")

    def test_raises_timeout_when_over_budget(self):
        ctx = CallContext(timeout=0.05)
        with self.assertRaises(Timeout):
            call(lambda: time.sleep(0.4), ctx=ctx)

    def test_context_call_uses_its_budget(self):
        ctx = CallContext(timeout=1.0)
        with self.assertRaises(Timeout):
            ctx.call(lambda: time.sleep(0.4), timeout=0.05)

    def test_without_deadline_waits_for_completion(self):
        ctx = CallContext()
        self.assertEqual(call(lambda: (time.sleep(0.05), "late")[1], ctx=ctx), "late")


class TestBudget(unittest.TestCase):
    def test_remaining_without_deadline_is_infinite(self):
        self.assertEqual(CallContext().remaining(), float("inf"))

    def test_remaining_shrinks_with_clock(self):
        clock = FakeClock(start=100.0)
        ctx = CallContext(clock=clock, timeout=5.0)
        clock.advance(2.0)
        self.assertAlmostEqual(ctx.remaining(), 3.0, places=6)

    def test_child_uses_parent_clock(self):
        clock = FakeClock(start=100.0)
        parent = CallContext(clock=clock, timeout=5.0)
        kid = parent.child(timeout=1.0)
        clock.advance(0.5)
        self.assertAlmostEqual(kid.remaining(), 0.5, places=6)

    def test_deadline_expires_after_clock_advance(self):
        clock = FakeClock(start=0.0)
        ctx = CallContext(clock=clock, timeout=1.0)
        self.assertFalse(ctx.expired())
        clock.advance(2.0)
        self.assertTrue(ctx.expired())


class TestCancel(unittest.TestCase):
    def test_cancel_sets_flag(self):
        ctx = CallContext(timeout=1.0)
        self.assertFalse(ctx.cancelled)
        ctx.cancel()
        self.assertTrue(ctx.cancelled)

    def test_cancel_propagates_to_existing_children(self):
        root = CallContext(timeout=5.0)
        mid = root.child(timeout=4.0)
        leaf = mid.child(timeout=3.0)
        root.cancel()
        self.assertTrue(mid.cancelled)
        self.assertTrue(leaf.cancelled)

    def test_cancel_propagates_to_later_children(self):
        root = CallContext(timeout=5.0)
        root.cancel()
        self.assertTrue(root.child(timeout=1.0).cancelled)

    def test_check_raises_after_cancel(self):
        ctx = CallContext(timeout=1.0)
        ctx.check()
        ctx.cancel()
        with self.assertRaises(Cancelled):
            ctx.check()


if __name__ == "__main__":
    unittest.main()
