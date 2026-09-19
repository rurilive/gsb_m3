"""rekey 子流程的行为测试：时钟注入定节奏。

覆盖：FULL/DEGRADED 两稳态成功路径、三步各自超时回退、回退后会话可用。
"""

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
    """握手到稳态，返回会话。"""
    s = Session(clock=clock)
    s.feed(Ev.START)
    s.feed(Ev.PEER_HELLO, suite)
    s.feed(Ev.PEER_KEY)
    s.feed(Ev.PEER_AUTH_OK)
    return s


def rekey_ok(s, clock, delays=(1.0, 1.0)):
    """在稳态上走完整 rekey：offer -> accept -> confirm -> done。"""
    s.feed(Ev.REKEY)
    clock.advance(delays[0])
    s.feed(Ev.PEER_REKEY_ACCEPT)
    clock.advance(delays[1])
    s.feed(Ev.PEER_REKEY_DONE)


class TestRekeySuccess(unittest.TestCase):
    def test_rekey_from_full_returns_full(self):
        clock = FakeClock()
        s = steady(clock, "strong")
        rekey_ok(s, clock)
        self.assertIs(s.state, State.FULL)
        self.assertEqual(s.suite, "strong")

    def test_rekey_from_degraded_returns_degraded(self):
        clock = FakeClock()
        s = steady(clock, "weak")
        rekey_ok(s, clock)
        self.assertIs(s.state, State.DEGRADED)
        self.assertEqual(s.suite, "weak")

    def test_rekey_sends_offer_and_confirm(self):
        clock = FakeClock()
        s = steady(clock)
        rekey_ok(s, clock)
        self.assertEqual(
            [m for _, m in s.outbox[-2:]],
            ["c_rekey_offer", "c_rekey_confirm"],
        )

    def test_rekey_move_details(self):
        clock = FakeClock()
        s = steady(clock)
        rekey_ok(s, clock)
        self.assertEqual(
            [e.detail for e in s.log if e.kind == "move"][-3:],
            [
                "FULL->REKEY_OFFER_SENT",
                "REKEY_OFFER_SENT->REKEY_CONFIRM_SENT",
                "REKEY_CONFIRM_SENT->FULL",
            ],
        )

    def test_rekey_states_during_flow(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.FULL)

    def test_rekey_timeout_constant(self):
        self.assertEqual(REKEY_TIMEOUT, 5.0)

    def test_rekey_remembers_resume_state(self):
        clock = FakeClock()
        s = steady(clock, "weak")
        s.feed(Ev.REKEY)
        self.assertIs(s.rekey_resume, State.DEGRADED)

    def test_rekey_success_no_timer_after_return(self):
        clock = FakeClock()
        s = steady(clock)
        rekey_ok(s, clock)
        clock.advance(100.0)
        s.poll()
        self.assertIs(s.state, State.FULL)


class TestRekeyStepTimeouts(unittest.TestCase):
    def test_offer_step_timeout_returns_full(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)
        self.assertEqual(s.suite, "strong")

    def test_offer_step_timeout_returns_degraded(self):
        clock = FakeClock()
        s = steady(clock, "weak")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)

    def test_confirm_step_timeout_returns_steady(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_offer_timeout_boundary(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT - 0.1)
        s.poll()
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        clock.advance(0.1)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_each_step_rearms_timer(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT - 0.1)
        s.poll()
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT - 0.1)
        s.poll()
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        clock.advance(0.1)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_timeout_logged_before_fallback_move(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertEqual(
            [e.kind for e in s.log[-2:]], ["timeout", "move"])
        self.assertEqual(
            s.log[-2].detail,
            f"TIMEOUT in {State.REKEY_OFFER_SENT.value}")
        self.assertEqual(
            s.log[-1].detail, "REKEY_OFFER_SENT->FULL")

    def test_timeout_discards_new_key_no_confirm_sent(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertEqual(
            [m for _, m in s.outbox],
            ["c_hello", "c_key", "c_auth", "c_rekey_offer"])

    def test_confirm_timeout_no_done_means_abort(self):
        clock = FakeClock()
        s = steady(clock, "weak")
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)


class TestRekeyUsableAfterFallback(unittest.TestCase):
    def test_connection_alive_after_timeout(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        s.feed(Ev.PEER_CLOSE)
        self.assertIs(s.state, State.CLOSED)
        self.assertEqual(s.outbox[-1], (clock.now, "c_close"))

    def test_rekey_again_after_timeout_succeeds(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)
        rekey_ok(s, clock)
        self.assertIs(s.state, State.FULL)

    def test_rekey_again_after_success(self):
        clock = FakeClock()
        s = steady(clock, "weak")
        rekey_ok(s, clock)
        rekey_ok(s, clock)
        self.assertIs(s.state, State.DEGRADED)

    def test_rekey_does_not_change_suite_on_timeout(self):
        clock = FakeClock()
        s = steady(clock, "weak")
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertEqual(s.suite, "weak")


class TestRekeyProtocol(unittest.TestCase):
    def test_accept_before_offer_rejected(self):
        clock = FakeClock()
        s = steady(clock)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.PEER_REKEY_ACCEPT)
        self.assertIs(s.state, State.FULL)

    def test_done_before_confirm_rejected(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.REKEY_OFFER_SENT)

    def test_rekey_rejected_from_closed(self):
        s = Session(clock=FakeClock())
        with self.assertRaises(ProtocolError):
            s.feed(Ev.REKEY)
        self.assertIs(s.state, State.CLOSED)

    def test_send_timestamps_follow_clock(self):
        clock = FakeClock()
        s = steady(clock)
        s.feed(Ev.REKEY)
        clock.advance(2.0)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        self.assertEqual(s.outbox[-1], (2.0, "c_rekey_confirm"))
        clock.advance(2.0)
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.FULL)


if __name__ == "__main__":
    unittest.main()
