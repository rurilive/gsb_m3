"""rekey 子流程的行为测试：稳态触发、三步协商、超时回退。"""

import unittest

from handshake import (
    REKEY_TIMEOUT,
    Ev,
    ProtocolError,
    Session,
    State,
)


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


def rekey_ok(s):
    """从稳态发起 rekey 并走完三步协商。"""
    s.feed(Ev.REKEY)
    s.feed(Ev.PEER_REKEY_ACCEPT)
    s.feed(Ev.PEER_REKEY_DONE)


class TestRekeySuccess(unittest.TestCase):
    def test_full_rekey_success_returns_full(self):
        s = steady(FakeClock(), "strong")
        rekey_ok(s)
        self.assertIs(s.state, State.FULL)
        self.assertEqual(s.suite, "strong")
        self.assertEqual(
            [m for _, m in s.outbox],
            ["c_hello", "c_key", "c_auth", "c_rekey_offer",
             "c_rekey_confirm"],
        )

    def test_degraded_rekey_success_returns_degraded(self):
        s = steady(FakeClock(), "weak")
        rekey_ok(s)
        self.assertIs(s.state, State.DEGRADED)
        self.assertEqual(s.suite, "weak")

    def test_offer_sent_on_rekey(self):
        s = steady(FakeClock())
        s.feed(Ev.REKEY)
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        self.assertEqual(s.outbox[-1], (0.0, "c_rekey_offer"))

    def test_confirm_sent_on_accept(self):
        s = steady(FakeClock())
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        self.assertEqual(s.outbox[-1], (0.0, "c_rekey_confirm"))

    def test_success_clears_resume_state(self):
        s = steady(FakeClock())
        rekey_ok(s)
        self.assertIsNone(s.resume_state)

    def test_move_log_sequence(self):
        s = steady(FakeClock())
        rekey_ok(s)
        self.assertEqual(
            [e.detail for e in s.log if e.kind == "move"][-3:],
            [
                "FULL->REKEY_OFFER_SENT",
                "REKEY_OFFER_SENT->REKEY_CONFIRM_SENT",
                "REKEY_CONFIRM_SENT->FULL",
            ],
        )


class TestRekeyTimeout(unittest.TestCase):
    def test_offer_step_timeout_returns_full(self):
        clock = FakeClock()
        s = steady(clock, "strong")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)
        self.assertEqual(
            s.log[-2].detail, f"TIMEOUT in {State.REKEY_OFFER_SENT.value}")
        self.assertEqual(
            [e.kind for e in s.log[-2:]], ["timeout", "move"])

    def test_confirm_step_timeout_returns_degraded(self):
        clock = FakeClock()
        s = steady(clock, "weak")
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)
        self.assertEqual(
            s.log[-2].detail,
            f"TIMEOUT in {State.REKEY_CONFIRM_SENT.value}")

    def test_timer_armed_at_each_step(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT - 0.1)
        s.poll()
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        # 第二步重新武装：旧 deadline 不会触发
        clock.advance(REKEY_TIMEOUT - 0.1)
        s.poll()
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        clock.advance(0.1)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_timeout_clears_resume_state(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIsNone(s.resume_state)

    def test_connection_survives_timeout(self):
        clock = FakeClock()
        s = steady(clock, "weak")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)
        # 回退后会话仍可用：再次 rekey 成功
        rekey_ok(s)
        self.assertIs(s.state, State.DEGRADED)
        # 对端关闭也照常工作
        s.feed(Ev.PEER_CLOSE)
        self.assertIs(s.state, State.CLOSED)


class TestRekeyProtocol(unittest.TestCase):
    def test_rekey_rejected_outside_steady(self):
        clock = FakeClock()
        s = Session(clock=clock)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.REKEY)
        s.feed(Ev.START)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.REKEY)
        self.assertIs(s.state, State.HELLO_SENT)

    def test_rekey_rejected_during_rekey(self):
        s = steady(FakeClock())
        s.feed(Ev.REKEY)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.REKEY)
        self.assertIs(s.state, State.REKEY_OFFER_SENT)

    def test_stray_accept_rejected_in_steady(self):
        s = steady(FakeClock())
        with self.assertRaises(ProtocolError):
            s.feed(Ev.PEER_REKEY_ACCEPT)
        self.assertIs(s.state, State.FULL)

    def test_stray_done_rejected_before_accept(self):
        s = steady(FakeClock())
        s.feed(Ev.REKEY)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.REKEY_OFFER_SENT)

    def test_rekey_timeout_constant(self):
        self.assertEqual(REKEY_TIMEOUT, 5.0)


if __name__ == "__main__":
    unittest.main()
