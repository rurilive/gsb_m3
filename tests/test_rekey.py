"""rekey 子流程的行为测试：时钟注入定节奏。"""

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


def rekey_success(s):
    """从稳态走完三步 rekey。"""
    s.feed(Ev.REKEY)
    s.feed(Ev.PEER_REKEY_ACCEPT)
    s.feed(Ev.PEER_REKEY_DONE)


class TestRekeySuccess(unittest.TestCase):
    def test_full_rekey_returns_full(self):
        s = steady(FakeClock(), "strong")
        rekey_success(s)
        self.assertIs(s.state, State.FULL)
        self.assertEqual(s.suite, "strong")

    def test_degraded_rekey_returns_degraded(self):
        s = steady(FakeClock(), "weak")
        rekey_success(s)
        self.assertIs(s.state, State.DEGRADED)
        self.assertEqual(s.suite, "weak")

    def test_rekey_message_sequence(self):
        s = steady(FakeClock())
        s.feed(Ev.REKEY)
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        self.assertEqual(s.outbox[-1], (0.0, "rekey-offer"))
        s.feed(Ev.PEER_REKEY_ACCEPT)
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        self.assertEqual(s.outbox[-1], (0.0, "rekey-confirm"))
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.FULL)
        self.assertEqual(
            [m for _, m in s.outbox],
            ["c_hello", "c_key", "c_auth", "rekey-offer", "rekey-confirm"])

    def test_rekey_moves_logged(self):
        s = steady(FakeClock())
        rekey_success(s)
        self.assertEqual(
            [e.detail for e in s.log if e.kind == "move"][-3:],
            [
                "FULL->REKEY_OFFER_SENT",
                "REKEY_OFFER_SENT->REKEY_CONFIRM_SENT",
                "REKEY_CONFIRM_SENT->FULL",
            ],
        )

    def test_rekey_disarms_timer_on_done(self):
        clock = FakeClock()
        s = steady(clock)
        rekey_success(s)
        clock.advance(REKEY_TIMEOUT + 100.0)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_rekey_not_allowed_outside_steady(self):
        clock = FakeClock()
        s = Session(clock=clock)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.REKEY)
        s.feed(Ev.START)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.REKEY)


class TestRekeyTimeout(unittest.TestCase):
    def test_offer_step_timeout_returns_full(self):
        clock = FakeClock()
        s = steady(clock, "strong")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_offer_step_timeout_returns_degraded(self):
        clock = FakeClock()
        s = steady(clock, "weak")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)

    def test_confirm_step_timeout_returns_full(self):
        clock = FakeClock()
        s = steady(clock, "strong")
        s.feed(Ev.REKEY)
        clock.advance(1.0)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_confirm_step_timeout_returns_degraded(self):
        clock = FakeClock()
        s = steady(clock, "weak")
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)

    def test_timer_armed_at_each_step(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT - 0.1)
        s.poll()
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        clock.advance(0.1)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT - 0.1)
        s.poll()
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        clock.advance(0.1)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_timeout_logged(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertEqual(
            [e.kind for e in s.log[-2:]], ["timeout", "move"])
        self.assertEqual(
            s.log[-2].detail, f"TIMEOUT in {State.REKEY_OFFER_SENT.value}")
        self.assertEqual(s.log[-1].detail, "REKEY_OFFER_SENT->FULL")

    def test_timeout_keeps_connection_open(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIn(s.state, (State.FULL, State.DEGRADED))
        self.assertFalse(s.state is State.CLOSED)


class TestRekeyAfterFallback(unittest.TestCase):
    def test_usable_after_offer_timeout(self):
        clock = FakeClock()
        s = steady(clock, "weak")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)
        rekey_success(s)
        self.assertIs(s.state, State.DEGRADED)

    def test_usable_after_confirm_timeout(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)
        rekey_success(s)
        self.assertIs(s.state, State.FULL)
        s.feed(Ev.PEER_CLOSE)
        self.assertIs(s.state, State.CLOSED)

    def test_stale_accept_after_fallback_raises(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        with self.assertRaises(ProtocolError):
            s.feed(Ev.PEER_REKEY_ACCEPT)
        self.assertIs(s.state, State.FULL)


if __name__ == "__main__":
    unittest.main()
