"""Short-lived access tokens and rotating, long-lived refresh tokens.

``TokenService`` sits on top of the stateless HMAC layer and the session
registry:

* ``issue`` opens a session and mints a pair: an access token (short
  TTL) and a refresh token (long TTL).
* ``verify_access`` checks signature, type and the expiry window and then
  confirms the session is still live and not revoked. All state lookups
  are dict hits keyed by session id, so cost does not grow with the
  number of sessions.
* ``refresh`` exchanges one refresh token for a brand new pair. The old
  refresh token dies immediately; presenting it again is treated as token
  theft and revokes the whole session.
* ``revoke_session`` closes the session and records a time-bounded
  tombstone, so every token of the session (including strings already in
  circulation) is refused.
* ``sweep`` removes sessions whose refresh token has aged out and
  tombstones that can no longer protect any live token.

Issuer and verifier clocks may disagree slightly: a configurable
``skew`` widens both the expiry and the not-before side of the window.
Tokens outside that window are refused.
"""

import secrets
import threading
from collections import namedtuple

from tokengate.clock import Clock
from tokengate.errors import (
    InvalidClaims,
    RefreshReused,
    SessionRevoked,
    TokenExpired,
    TokenNotYetValid,
    UnknownSession,
    WrongTokenType,
)
from tokengate.revoke import RevocationList
from tokengate.store import SessionStore
from tokengate.token import DEFAULT_KID, sign_payload, verify_token

TYPE_ACCESS = "access"
TYPE_REFRESH = "refresh"

DEFAULT_ACCESS_TTL = 15 * 60
DEFAULT_REFRESH_TTL = 14 * 24 * 60 * 60
DEFAULT_SKEW = 30

JTI_BYTES = 16

TokenPair = namedtuple(
    "TokenPair",
    ("sid", "access_token", "refresh_token",
     "access_exp", "refresh_exp", "access_jti", "refresh_jti"),
)

SweepReport = namedtuple(
    "SweepReport",
    ("sessions_removed", "sessions_remaining",
     "revocations_removed", "revocations_remaining"),
)


def new_jti():
    """Fresh, unguessable token id (per-token, refresh rotation uses it)."""
    return secrets.token_urlsafe(JTI_BYTES)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class TokenService:
    """Issues, verifies, rotates, revokes and sweeps session tokens."""

    def __init__(self, keyring, clock=None, store=None, revocations=None,
                 access_ttl=DEFAULT_ACCESS_TTL, refresh_ttl=DEFAULT_REFRESH_TTL,
                 skew=DEFAULT_SKEW, kid=DEFAULT_KID):
        if access_ttl <= 0:
            raise ValueError("access_ttl must be positive")
        if refresh_ttl <= 0:
            raise ValueError("refresh_ttl must be positive")
        if skew < 0:
            raise ValueError("skew must be non-negative")
        self._keyring = keyring
        self._store = store if store is not None else SessionStore(clock or Clock())
        self._clock = self._store.clock
        self._revocations = revocations if revocations is not None else RevocationList(self._clock)
        self._revocations.bind_clock(self._clock)
        self._access_ttl = float(access_ttl)
        self._refresh_ttl = float(refresh_ttl)
        self._skew = float(skew)
        self._kid = kid
        self._lock = threading.RLock()
        # No-op seam tests use to pause inside the locked critical
        # section and force a specific interleaving.
        self._on_rotate_hook = lambda: None
        self._on_revoke_hook = lambda: None

    def set_test_hooks(self, on_rotate=None, on_revoke=None):
        """Install critical-section hooks (testing only)."""
        self._on_rotate_hook = on_rotate or (lambda: None)
        self._on_revoke_hook = on_revoke or (lambda: None)

    @property
    def clock(self):
        return self._clock

    @property
    def store(self):
        return self._store

    @property
    def revocations(self):
        return self._revocations

    @property
    def access_ttl(self):
        return self._access_ttl

    @property
    def refresh_ttl(self):
        return self._refresh_ttl

    @property
    def skew(self):
        return self._skew

    def issue(self, claims=None, sid=None, kid=None):
        """Open a session and return its first (access, refresh) pair."""
        with self._lock:
            now = self._clock.now()
            session = self._store.open(claims, sid=sid)
            return self._mint(session, now, kid or self._kid)

    def verify_access(self, token):
        """Verify an access token; return its payload dict or raise.

        Raises MalformedToken, UnknownKey, InvalidSignature,
        WrongTokenType, InvalidClaims, TokenExpired/TokenNotYetValid,
        SessionRevoked or UnknownSession.
        """
        payload, sid, _jti, exp, iat = self._decode(token, TYPE_ACCESS)
        with self._lock:
            now = self._clock.now()
            self._check_window(iat, exp, now)
            if self._revocations.is_revoked(sid):
                raise SessionRevoked("session has been revoked: %r" % (sid,))
            self._store.require(sid)
            return dict(payload)

    def refresh(self, token, kid=None):
        """Exchange a valid refresh token for a fresh pair.

        The presented token's jti must match the session's current one.
        Any older (or unknown) refresh token is a reuse attempt: the
        session is revoked and RefreshReused is raised.
        """
        _payload, sid, jti, exp, iat = self._decode(token, TYPE_REFRESH)
        with self._lock:
            now = self._clock.now()
            self._check_window(iat, exp, now)
            if self._revocations.is_revoked(sid):
                raise SessionRevoked("session has been revoked: %r" % (sid,))
            session = self._store.get(sid)
            if session is None:
                raise UnknownSession("unknown session id: %r" % (sid,))
            if session.refresh_jti is None or jti != session.refresh_jti:
                self._revoke(session, now)
                raise RefreshReused("stale or unknown refresh token for session %r" % (sid,))
            pair = self._mint(session, now, kid or self._kid)
            self._on_rotate_hook()
            return pair

    def revoke_session(self, sid):
        """Close a session and tombstone it; True when one was live.

        Idempotent: revoking an unknown, already closed or swept id
        returns False and changes nothing.
        """
        with self._lock:
            now = self._clock.now()
            session = self._store.get(sid)
            if session is None:
                return False
            self._on_revoke_hook()
            self._revoke(session, now)
            return True

    def sweep(self, now=None):
        """Drop aged-out sessions and tombstones; return a SweepReport.

        A session is removed only once its refresh token is outside the
        skew window, so nothing that could still verify is collected.
        """
        with self._lock:
            if now is None:
                now = self._clock.now()
            expired_sids = [
                sid for sid in self._store.sids()
                if (record := self._store.get(sid)) is not None
                and record.refresh_exp is not None
                and record.refresh_exp + self._skew < now
            ]
            for sid in expired_sids:
                self._store.close(sid)
            revocations = self._revocations.sweep(now)
            return SweepReport(
                sessions_removed=len(expired_sids),
                sessions_remaining=len(self._store),
                revocations_removed=revocations["removed"],
                revocations_remaining=revocations["remaining"],
            )

    def _mint(self, session, now, kid):
        access_jti = new_jti()
        refresh_jti = new_jti()
        access_exp = now + self._access_ttl
        refresh_exp = now + self._refresh_ttl
        access_payload = dict(session.claims)
        access_payload.update({
            "typ": TYPE_ACCESS,
            "sid": session.sid,
            "iat": now,
            "exp": access_exp,
            "jti": access_jti,
        })
        refresh_payload = {
            "typ": TYPE_REFRESH,
            "sid": session.sid,
            "iat": now,
            "exp": refresh_exp,
            "jti": refresh_jti,
        }
        access_token = sign_payload(access_payload, self._keyring, kid)
        refresh_token = sign_payload(refresh_payload, self._keyring, kid)
        session.refresh_jti = refresh_jti
        session.refresh_exp = refresh_exp
        session.last_rotated_at = now
        return TokenPair(
            sid=session.sid,
            access_token=access_token,
            refresh_token=refresh_token,
            access_exp=access_exp,
            refresh_exp=refresh_exp,
            access_jti=access_jti,
            refresh_jti=refresh_jti,
        )

    def _revoke(self, session, now):
        bound = max(now + self._refresh_ttl, session.refresh_exp or 0.0) + self._skew
        self._store.close(session.sid)
        self._revocations.revoke(session.sid, bound)

    def _check_window(self, iat, exp, now):
        if exp + self._skew < now:
            raise TokenExpired("token expired at %r" % (exp,))
        if iat is not None and iat - self._skew > now:
            raise TokenNotYetValid("token valid only from %r" % (iat,))

    def _decode(self, token, expected_type):
        payload = verify_token(token, self._keyring)
        typ = payload.get("typ")
        if typ != expected_type:
            raise WrongTokenType(
                "expected a %r token, got %r" % (expected_type, typ))
        sid = payload.get("sid")
        jti = payload.get("jti")
        exp = payload.get("exp")
        iat = payload.get("iat")
        if not isinstance(sid, str) or not sid:
            raise InvalidClaims("token payload lacks a string sid")
        if not isinstance(jti, str) or not jti:
            raise InvalidClaims("token payload lacks a string jti")
        if not _is_number(exp):
            raise InvalidClaims("token payload lacks a numeric exp")
        if iat is not None and not _is_number(iat):
            raise InvalidClaims("token payload carries a non-numeric iat")
        return payload, sid, jti, exp, iat
