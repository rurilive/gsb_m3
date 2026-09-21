"""Differential testing against a deliberately naive implementation.

The reference model keeps every live session and tombstone in plain lists
and answers every question by scanning them end to end. Random streams of
issue / verify / rotate / reuse / revoke / sweep / tick operations are
replayed against both it and TokenService; every verdict and every bit of
final state must agree.
"""

import random
import unittest

from tokengate import (
    InvalidClaims,
    InvalidSignature,
    KeyRing,
    MalformedToken,
    ManualClock,
    RefreshReused,
    SessionRevoked,
    TokenNotYetValid,
    TokenExpired,
    TokenService,
    UnknownKey,
    UnknownSession,
    WrongTokenType,
)
from tokengate import token as token_mod


class NaiveModel:
    """Full-table-scan reimplementation of the TokenService semantics."""

    def __init__(self, keyring, clock, access_ttl, refresh_ttl, skew):
        self.keyring = keyring
        self.clock = clock
        self.access_ttl = float(access_ttl)
        self.refresh_ttl = float(refresh_ttl)
        self.skew = float(skew)
        # sid -> {"claims", "refresh_jti", "refresh_exp"}
        self.live = {}
        # sid -> keep-until bound
        self.revoked = {}

    def issue(self, claims, sid, pair):
        self.live[sid] = {
            "claims": dict(claims),
            "refresh_jti": pair.refresh_jti,
            "refresh_exp": pair.refresh_exp,
        }

    def _decode(self, token, expected_type):
        payload = token_mod.verify_token(token, self.keyring)
        typ = payload.get("typ")
        if typ != expected_type:
            raise WrongTokenType("naive: wrong type %r" % (typ,))
        sid = payload.get("sid")
        jti = payload.get("jti")
        exp = payload.get("exp")
        iat = payload.get("iat")
        if not isinstance(sid, str) or not sid:
            raise InvalidClaims("naive: bad sid")
        if not isinstance(jti, str) or not jti:
            raise InvalidClaims("naive: bad jti")
        if not isinstance(exp, (int, float)) or isinstance(exp, bool):
            raise InvalidClaims("naive: bad exp")
        if iat is not None and (not isinstance(iat, (int, float))
                                or isinstance(iat, bool)):
            raise InvalidClaims("naive: bad iat")
        return payload, sid, jti, exp, iat

    def _window(self, iat, exp):
        now = self.clock.now()
        if exp + self.skew < now:
            raise TokenExpired("naive: expired")
        if iat is not None and iat - self.skew > now:
            raise TokenNotYetValid("naive: future token")

    def verify_access(self, token):
        payload, sid, _jti, exp, iat = self._decode(token, "access")
        self._window(iat, exp)
        # Linear scan: any tombstone for this sid?
        for revoked_sid in self.revoked:
            if revoked_sid == sid:
                raise SessionRevoked("naive: revoked")
        for live_sid, record in self.live.items():
            if live_sid == sid:
                return dict(payload)
        raise UnknownSession("naive: unknown sid")

    def observe_refresh(self, sid, success, new_pair=None):
        """Mirror the state transition the real service just committed."""
        if success:
            self.live[sid]["refresh_jti"] = new_pair.refresh_jti
            self.live[sid]["refresh_exp"] = new_pair.refresh_exp
        else:
            record = self.live.pop(sid, None)
            bound = max(self.clock.now() + self.refresh_ttl,
                        record["refresh_exp"] if record else 0.0) + self.skew
            old_bound = self.revoked.get(sid)
            if old_bound is None or bound > old_bound:
                self.revoked[sid] = bound

    def decide_refresh(self, token):
        """Decision a naive verifier gives for a refresh attempt.

        Never raises: cryptographic/structural/window failures come back
        as ``("error", exception_class)``.
        """
        try:
            _payload, sid, jti, exp, iat = self._decode(token, "refresh")
            self._window(iat, exp)
        except Exception as exc:  # noqa: BLE001 - reported as a decision
            return ("error", type(exc))
        for revoked_sid in self.revoked:
            if revoked_sid == sid:
                return ("revoked", SessionRevoked)
        record = self.live.get(sid)
        if record is None:
            return ("unknown", UnknownSession)
        if jti != record["refresh_jti"]:
            return ("reused", RefreshReused)
        return ("ok", record)

    def revoke(self, sid):
        record = self.live.pop(sid, None)
        if record is None:
            return False
        bound = max(self.clock.now() + self.refresh_ttl,
                    record["refresh_exp"]) + self.skew
        old_bound = self.revoked.get(sid)
        if old_bound is None or bound > old_bound:
            self.revoked[sid] = bound
        return True

    def sweep(self):
        now = self.clock.now()
        dead = [sid for sid, rec in self.live.items()
                if rec["refresh_exp"] + self.skew < now]
        for sid in dead:
            del self.live[sid]
        expired = [sid for sid, bound in self.revoked.items() if bound < now]
        for sid in expired:
            del self.revoked[sid]
        return len(dead), len(self.live), len(expired), len(self.revoked)


def verdict(call):
    """(kind, type-or-payload) produced by running one service call."""
    try:
        result = call()
    except Exception as exc:  # noqa: BLE001 - compared as a verdict
        return ("error", type(exc))
    return ("ok", result)


def tampered(token, rng):
    head, body, sig = token.split(".")
    choice = rng.randrange(3)
    if choice == 0:
        flipped = "A" if sig[0] != "A" else "B"
        return ".".join([head, body, flipped + sig[1:]])
    if choice == 1:
        flipped = "A" if body[0] != "A" else "B"
        return ".".join([head, flipped + body[1:], sig])
    return token + "x"


class DifferentialTests(unittest.TestCase):
    def run_scenario(self, seed, steps=500):
        rng = random.Random(seed)
        clock = ManualClock(1_000_000.0)
        ring = KeyRing({"k1": "ring-secret-%d" % seed})
        svc = TokenService(
            ring, clock,
            access_ttl=rng.choice([5, 20, 60]),
            refresh_ttl=rng.choice([50, 200, 1000]),
            skew=rng.choice([0, 1, 5]),
        )
        naive = NaiveModel(
            ring, clock,
            access_ttl=svc.access_ttl, refresh_ttl=svc.refresh_ttl,
            skew=svc.skew,
        )
        # Issued tokens: token string -> ("access"|"refresh", sid)
        tokens = {}
        sids = []
        claim_id = 0

        for _ in range(steps):
            action = rng.randrange(9)

            if action == 0:  # issue
                claim_id += 1
                claims = {"sub": "u-%d" % claim_id, "n": claim_id}
                pair = svc.issue(claims)
                naive.issue(claims, pair.sid, pair)
                tokens[pair.access_token] = ("access", pair.sid)
                tokens[pair.refresh_token] = ("refresh", pair.sid)
                sids.append(pair.sid)

            elif action == 1 and tokens:  # verify a random access token
                accesses = [t for t, kind in tokens.items() if kind[0] == "access"]
                if accesses:
                    token = rng.choice(accesses)
                    real = verdict(lambda: svc.verify_access(token))
                    model = verdict(lambda: naive.verify_access(token))
                    self._assert_same_verdict(real, model, seed, "verify_access")

            elif action == 2 and tokens:  # refresh with a random token
                refreshes = [t for t, kind in tokens.items() if kind[0] == "refresh"]
                if refreshes:
                    token = rng.choice(refreshes)
                    sid = tokens[token][1]
                    real = verdict(lambda: svc.refresh(token))
                    decision, detail = naive.decide_refresh(token)
                    if decision == "ok":
                        self.assertEqual(real[0], "ok", (seed, real))
                        result_pair = real[1]
                        naive.observe_refresh(sid, True, new_pair=result_pair)
                        tokens[result_pair.access_token] = ("access", sid)
                        tokens[result_pair.refresh_token] = ("refresh", sid)
                    else:
                        self.assertEqual(real[0], "error", (seed, real))
                        if decision == "reused":
                            self.assertIs(real[1], RefreshReused, (seed, real))
                            naive.observe_refresh(sid, False)
                        else:
                            self.assertIs(real[1], detail, (seed, real, decision))

            elif action == 3 and sids:  # revoke
                sid = rng.choice(sids)
                self.assertIs(svc.revoke_session(sid), naive.revoke(sid), seed)

            elif action == 4:  # sweep
                report = svc.sweep()
                totals = naive.sweep()
                self.assertEqual(
                    (report.sessions_removed, report.sessions_remaining,
                     report.revocations_removed, report.revocations_remaining),
                    totals, seed,
                )

            elif action == 5:  # time advances
                clock.advance(rng.choice([1, 3, 7, 25, 120, 500]))

            elif action == 6 and tokens:  # tampered token
                token = rng.choice(list(tokens))
                kind = tokens[token][0]
                bad = tampered(token, rng)
                call = (svc.verify_access if kind == "access"
                        else svc.refresh)
                real = verdict(lambda: call(bad))
                self.assertEqual(real[0], "error", seed)
                self.assertIn(
                    real[1],
                    (InvalidSignature, MalformedToken),
                    (seed, real[1]),
                )

            elif action == 7:  # structurally bogus input
                junk = rng.choice(["", "a.b", "...", "not-a-token", "a.b.c"])
                real = verdict(lambda: svc.verify_access(junk))
                model = verdict(lambda: naive.verify_access(junk))
                self.assertEqual(real, model, seed)

            else:  # unknown key: drop k1 then keep using old tokens
                if "k1" in ring:
                    ring.drop("k1")
                if tokens:
                    token = next(iter(tokens))
                    kind = tokens[token][0]
                    call = (svc.verify_access if kind == "access"
                            else svc.refresh)
                    real = verdict(lambda: call(token))
                    if kind == "access":
                        model = verdict(lambda: naive.verify_access(token))
                        self.assertEqual(real[0], model[0], seed)
                    else:
                        decision, _detail = naive.decide_refresh(token)
                        self.assertEqual(real[0],
                                         "ok" if decision == "ok" else "error",
                                         seed)
                    if real[0] == "error":
                        self.assertIs(real[1], UnknownKey)
                        if kind == "access":
                            self.assertIs(model[1], UnknownKey)
                ring.add("k1", "ring-secret-%d" % seed)

        # Final state agreement.
        self.assertEqual(sorted(svc.store.sids()), sorted(naive.live), seed)
        self.assertEqual(sorted(svc.revocations.sids()),
                         sorted(naive.revoked), seed)
        for sid, record in naive.live.items():
            session = svc.store.require(sid)
            self.assertEqual(session.refresh_jti, record["refresh_jti"],
                             (seed, sid))
            self.assertEqual(session.refresh_exp, record["refresh_exp"],
                             (seed, sid))
        for sid, bound in naive.revoked.items():
            self.assertEqual(svc.revocations.expires_at(sid), bound,
                             (seed, sid))

    def _assert_same_verdict(self, real, model, seed, where):
        self.assertEqual(real[0], model[0], (seed, where, real, model))
        if real[0] == "error":
            self.assertIs(real[1], model[1], (seed, where, real, model))

    def test_many_random_histories(self):
        for seed in range(60):
            self.run_scenario(seed)


if __name__ == "__main__":
    unittest.main()
