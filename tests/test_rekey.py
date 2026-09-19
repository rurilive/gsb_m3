"""rekey 子流程的行为测试：成功路径、各步超时回退、回退后可用。"""

import unittest

from handshake import Ev, ProtocolError, REKEY_TIMEOUT, Session, State


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


def steady(clock, suite="strong"):
    """走完整握手进入稳态，返回会话。"""
    s = Session(clock=clock)
    s.feed(Ev.START)
    s.feed(Ev.PEER_HELLO, suite)
    s.feed(Ev.PEER_KEY)
    s.feed(Ev.PEER_AUTH_OK)
    return s


def in_rekey(clock, suite="strong"):
    """进入稳态后触发 rekey，返回会话。"""
    s = steady(clock, suite)
    s.feed(Ev.REKEY)
    return s


class TestRekeySuccess(unittest.TestCase):
    def test_full_rekey_success_returns_full(self):
        s = in_rekey(FakeClock(), "strong")
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        s.feed(Ev.PEER_REKEY_ACCEPT, "key-2")
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.FULL)
        self.assertEqual(s.key, "key-2")

    def test_degraded_rekey_success_returns_degraded(self):
        s = in_rekey(FakeClock(), "weak")
        s.feed(Ev.PEER_REKEY_ACCEPT, "key-2")
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.DEGRADED)
        self.assertEqual(s.key, "key-2")

    def test_rekey_sends_offer_then_confirm(self):
        s = in_rekey(FakeClock())
        s.feed(Ev.PEER_REKEY_ACCEPT, "key-2")
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertEqual(
            [m for _, m in s.outbox],
            ["c_hello", "c_key", "c_auth", "c_rekey_offer", "c_rekey_confirm"])

    def test_return_move_logged_with_dynamic_target(self):
        s = in_rekey(FakeClock(), "weak")
        s.feed(Ev.PEER_REKEY_ACCEPT, "key-2")
        s.feed(Ev.PEER_REKEY_DONE)
        moves = [e.detail for e in s.log if e.kind == "move"]
        self.assertEqual(moves[-1], "REKEY_CONFIRM_SENT->DEGRADED")


class TestRekeyTimeout(unittest.TestCase):
    def test_offer_step_timeout_returns_full(self):
        clock = FakeClock()
        s = in_rekey(clock, "strong")
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)
        self.assertIsNone(s.key)

    def test_confirm_step_timeout_returns_degraded(self):
        clock = FakeClock()
        s = in_rekey(clock, "weak")
        s.feed(Ev.PEER_REKEY_ACCEPT, "key-2")
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)
        self.assertIsNone(s.key)  # 暂存的新密钥被丢弃

    def test_timer_rearmed_each_step(self):
        clock = FakeClock()
        s = in_rekey(clock)
        clock.advance(REKEY_TIMEOUT - 0.1)
        s.feed(Ev.PEER_REKEY_ACCEPT, "key-2")  # 第一步时限内完成，重新武装
        clock.advance(REKEY_TIMEOUT - 0.1)
        s.poll()
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        clock.advance(0.1)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_timeout_logged(self):
        clock = FakeClock()
        s = in_rekey(clock)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertEqual(s.log[-2].kind, "timeout")
        self.assertEqual(
            s.log[-2].detail, f"TIMEOUT in {State.REKEY_OFFER_SENT.value}")

    def test_session_usable_after_fallback(self):
        clock = FakeClock()
        s = in_rekey(clock)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)
        # 连接不断：可以再次发起 rekey 并走通
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT, "key-3")
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.FULL)
        self.assertEqual(s.key, "key-3")

    def test_steady_events_still_work_after_fallback(self):
        clock = FakeClock()
        s = in_rekey(clock)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        s.feed(Ev.PEER_CLOSE)
        self.assertIs(s.state, State.CLOSED)
        self.assertEqual(s.outbox[-1][1], "c_close")


class TestRekeyProtocol(unittest.TestCase):
    def test_rekey_rejected_outside_steady(self):
        clock = FakeClock()
        s = Session(clock=clock)
        s.feed(Ev.START)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.REKEY)
        self.assertIs(s.state, State.HELLO_SENT)

    def test_no_rekey_reentry(self):
        s = in_rekey(FakeClock())
        with self.assertRaises(ProtocolError):
            s.feed(Ev.REKEY)
        self.assertIs(s.state, State.REKEY_OFFER_SENT)

    def test_rekey_timeout_constant(self):
        self.assertEqual(REKEY_TIMEOUT, 5.0)


if __name__ == "__main__":
    unittest.main()
