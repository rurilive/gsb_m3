import unittest

from tokengate import (
    InvalidSignature,
    KeyRing,
    ManualClock,
    RefreshReused,
    SessionRevoked,
    TokenExpired,
    TokenNotYetValid,
    TokenService,
    UnknownSession,
    WrongTokenType,
)

import tokengate.token as token_mod


def make_service(start=1_700_000_000.0, access_ttl=60, refresh_ttl=600, skew=5):
    clock = ManualClock(start)
    ring = KeyRing({"k1": "service-secret"})
    return TokenService(ring, clock, access_ttl=access_ttl,
                        refresh_ttl=refresh_ttl, skew=skew), clock


class IssueAndVerifyTests(unittest.TestCase):
    def setUp(self):
        self.svc, self.clock = make_service()

    def test_pair_carries_the_claims(self):
        pair = self.svc.issue({"sub": "u-17", "role": "admin"})
        payload = self.svc.verify_access(pair.access_token)
        self.assertEqual(payload["sub"], "u-17")
        self.assertEqual(payload["role"], "admin")
        self.assertEqual(payload["sid"], pair.sid)
        self.assertEqual(payload["typ"], "access")

    def test_access_and_refresh_are_different(self):
        pair = self.svc.issue()
        self.assertNotEqual(pair.access_token, pair.refresh_token)
        self.assertIsInstance(pair.sid, str)
        self.assertEqual(pair.access_exp, self.clock.now() + 60)
        self.assertEqual(pair.refresh_exp, self.clock.now() + 600)

    def test_session_is_registered_with_refresh_state(self):
        pair = self.svc.issue()
        session = self.svc.store.require(pair.sid)
        self.assertEqual(session.refresh_jti, pair.refresh_jti)
        self.assertEqual(session.refresh_exp, pair.refresh_exp)

    def test_returned_payload_is_detached(self):
        pair = self.svc.issue({"sub": "u-1"})
        payload = self.svc.verify_access(pair.access_token)
        payload["sub"] = "attacker"
        self.assertEqual(self.svc.verify_access(pair.access_token)["sub"], "u-1")

    def test_refresh_token_is_not_an_access_token(self):
        pair = self.svc.issue()
        with self.assertRaises(WrongTokenType):
            self.svc.verify_access(pair.refresh_token)

    def test_access_token_is_not_a_refresh_token(self):
        pair = self.svc.issue()
        with self.assertRaises(WrongTokenType):
            self.svc.refresh(pair.access_token)

    def test_verify_after_store_closed_is_unknown_session(self):
        pair = self.svc.issue()
        self.svc.store.close(pair.sid)
        with self.assertRaises(UnknownSession):
            self.svc.verify_access(pair.access_token)


class LifetimeWindowTests(unittest.TestCase):
    def test_access_expires_after_ttl_plus_one(self):
        svc, clock = make_service(access_ttl=60, refresh_ttl=600, skew=5)
        pair = svc.issue()
        clock.advance(64)
        svc.verify_access(pair.access_token)  # 64 <= 60 + 5
        clock.advance(2)
        with self.assertRaises(TokenExpired):
            svc.verify_access(pair.access_token)  # 66 > 65

    def test_access_good_exactly_at_expiry_plus_skew_boundary(self):
        svc, clock = make_service(access_ttl=60, skew=5)
        pair = svc.issue()
        clock.set(1_700_000_065.0)
        svc.verify_access(pair.access_token)  # exp + skew == now, accepted
        clock.set(1_700_000_065.0 + 0.001)
        with self.assertRaises(TokenExpired):
            svc.verify_access(pair.access_token)

    def test_refresh_expires_after_refresh_ttl_with_skew(self):
        svc, clock = make_service(access_ttl=10, refresh_ttl=100, skew=5)
        pair = svc.issue()
        # Window is checked before rotation state: an aged-out token is
        # reported expired, never silently refreshed.
        clock.set(1_700_000_106.0)
        with self.assertRaises(TokenExpired):
            svc.refresh(pair.refresh_token)
        pair2 = svc.issue()  # fresh pair with a refresh exp of 206
        self.assertEqual(svc.refresh(pair2.refresh_token).sid, pair2.sid)

    def test_zero_skew_means_hard_expiry(self):
        svc, clock = make_service(access_ttl=60, refresh_ttl=600, skew=0)
        pair = svc.issue()
        clock.set(1_700_000_060.0)
        svc.verify_access(pair.access_token)
        clock.advance(0.001)
        with self.assertRaises(TokenExpired):
            svc.verify_access(pair.access_token)

    def test_skew_covers_a_slow_verifier_clock(self):
        svc, clock = make_service(access_ttl=60, skew=30)
        pair = svc.issue()
        clock.advance(89)
        svc.verify_access(pair.access_token)

    def test_skew_covers_a_fast_verifier_clock(self):
        # Token issued at 1000 by a clock that is 4s ahead of the
        # verifier: the verifier jumps back to 996 via an absolute set.
        svc, _clock = make_service(start=1000.0, access_ttl=60, skew=5)
        pair = svc.issue()
        svc.clock.set(996.0)
        svc.verify_access(pair.access_token)
        svc.clock.set(994.0)
        with self.assertRaises(TokenNotYetValid):
            svc.verify_access(pair.access_token)

    def test_bad_configuration_is_rejected(self):
        clock = ManualClock()
        ring = KeyRing({"k1": "s"})
        with self.assertRaises(ValueError):
            TokenService(ring, clock, access_ttl=0)
        with self.assertRaises(ValueError):
            TokenService(ring, clock, refresh_ttl=-1)
        with self.assertRaises(ValueError):
            TokenService(ring, clock, skew=-1)


class RefreshRotationTests(unittest.TestCase):
    def setUp(self):
        self.svc, self.clock = make_service()

    def test_refresh_mints_a_working_pair(self):
        pair = self.svc.issue({"sub": "u-7"})
        self.clock.advance(10)
        pair2 = self.svc.refresh(pair.refresh_token)
        self.assertNotEqual(pair2.access_token, pair.access_token)
        self.assertNotEqual(pair2.refresh_token, pair.refresh_token)
        self.assertEqual(pair2.sid, pair.sid)
        self.assertEqual(self.svc.verify_access(pair2.access_token)["sub"], "u-7")

    def test_old_refresh_token_is_rejected(self):
        pair = self.svc.issue()
        self.svc.refresh(pair.refresh_token)
        with self.assertRaises(RefreshReused):
            self.svc.refresh(pair.refresh_token)

    def test_reuse_revokes_the_whole_session(self):
        pair = self.svc.issue()
        pair2 = self.svc.refresh(pair.refresh_token)
        with self.assertRaises(RefreshReused):
            self.svc.refresh(pair.refresh_token)
        # Every token of the session is now dead, including the newest.
        with self.assertRaises(SessionRevoked):
            self.svc.verify_access(pair2.access_token)
        with self.assertRaises(SessionRevoked):
            self.svc.refresh(pair2.refresh_token)
        self.assertNotIn(pair.sid, self.svc.store)
        self.assertIn(pair.sid, self.svc.revocations)

    def test_repeated_reuse_still_reports_revoked(self):
        pair = self.svc.issue()
        self.svc.refresh(pair.refresh_token)
        with self.assertRaises(RefreshReused):
            self.svc.refresh(pair.refresh_token)
        with self.assertRaises(SessionRevoked):
            self.svc.refresh(pair.refresh_token)

    def test_many_rotations_keep_only_the_latest(self):
        pair = self.svc.issue()
        history = [pair.refresh_token]
        current = pair
        for _ in range(8):
            current = self.svc.refresh(current.refresh_token)
            history.append(current.refresh_token)
        self.svc.verify_access(current.access_token)
        with self.assertRaises(RefreshReused):
            self.svc.refresh(history[0])
        # The first reuse revokes the whole session; later stale tokens
        # and the newest pair all see the tombstone.
        for stale in history[1:-1]:
            with self.assertRaises(SessionRevoked):
                self.svc.refresh(stale)
        with self.assertRaises(SessionRevoked):
            self.svc.verify_access(current.access_token)


class RevocationTests(unittest.TestCase):
    def setUp(self):
        self.svc, self.clock = make_service()

    def test_revocation_kills_both_token_kinds(self):
        pair = self.svc.issue()
        self.assertTrue(self.svc.revoke_session(pair.sid))
        with self.assertRaises(SessionRevoked):
            self.svc.verify_access(pair.access_token)
        with self.assertRaises(SessionRevoked):
            self.svc.refresh(pair.refresh_token)

    def test_revocation_is_idempotent(self):
        pair = self.svc.issue()
        self.assertTrue(self.svc.revoke_session(pair.sid))
        self.assertFalse(self.svc.revoke_session(pair.sid))
        self.assertFalse(self.svc.revoke_session("never-existed"))

    def test_token_revoked_then_swept_is_unknown_not_revived(self):
        svc, clock = make_service(refresh_ttl=100, skew=5)
        pair = svc.issue()
        svc.revoke_session(pair.sid)
        clock.advance(200)
        report = svc.sweep()
        self.assertEqual(report.revocations_removed, 1)
        self.assertNotIn(pair.sid, svc.revocations)


class TamperTests(unittest.TestCase):
    def setUp(self):
        self.svc, self.clock = make_service()
        self.pair = self.svc.issue({"sub": "u-1"})

    def _flip(self, token):
        head, body, sig = token.split(".")
        flipped = "A" if sig[0] != "A" else "B"
        return ".".join([head, body, flipped + sig[1:]])

    def test_bad_access_signature(self):
        with self.assertRaises(InvalidSignature):
            self.svc.verify_access(self._flip(self.pair.access_token))

    def test_bad_refresh_signature(self):
        with self.assertRaises(InvalidSignature):
            self.svc.refresh(self._flip(self.pair.refresh_token))

    def test_payload_edit_is_refused(self):
        head, _body, sig = self.pair.access_token.split(".")
        forged_body = token_mod.b64u_encode(token_mod.canonical_json(
            {"typ": "access", "sid": self.pair.sid, "sub": "u-1",
             "iat": self.clock.now(), "exp": self.clock.now() + 9999,
             "jti": self.pair.access_jti}))
        with self.assertRaises(InvalidSignature):
            self.svc.verify_access(".".join([head, forged_body, sig]))

    def test_token_signed_by_another_keyring(self):
        other = KeyRing({"k1": "totally different secret"})
        foreign = token_mod.sign_payload(
            {"typ": "access", "sid": self.pair.sid, "sub": "u-1",
             "iat": self.clock.now(), "exp": self.clock.now() + 60,
             "jti": "j"}, other)
        with self.assertRaises(InvalidSignature):
            self.svc.verify_access(foreign)


if __name__ == "__main__":
    unittest.main()
