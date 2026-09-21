"""tokengate: HMAC signed tokens and a tiny in-memory session registry.

Public surface:

    KeyRing              secrets addressed by key id
    sign_payload         payload dict -> token string
    verify_token         token string -> payload dict, or raises TokenError
    SessionStore         live session registry
    RevocationList       per-session revocation tombstones, O(1) lookup
    TokenService         short access / long rotating refresh token pairs
    Clock, ManualClock   injectable time sources
"""

from tokengate.clock import Clock, ManualClock
from tokengate.errors import (
    InvalidClaims,
    InvalidSignature,
    MalformedToken,
    RefreshReused,
    SessionRevoked,
    TokenError,
    TokenExpired,
    TokenNotYetValid,
    UnknownKey,
    UnknownSession,
    WrongTokenType,
)
from tokengate.keys import KeyRing
from tokengate.revoke import RevocationList
from tokengate.session import (
    DEFAULT_ACCESS_TTL,
    DEFAULT_REFRESH_TTL,
    DEFAULT_SKEW,
    SweepReport,
    TokenPair,
    TokenService,
    new_jti,
)
from tokengate.store import Session, SessionStore, new_sid
from tokengate.token import (
    ALGORITHM,
    FORMAT_VERSION,
    canonical_json,
    sign_payload,
    split_token,
    verify_token,
)

__all__ = [
    "ALGORITHM",
    "FORMAT_VERSION",
    "DEFAULT_ACCESS_TTL",
    "DEFAULT_REFRESH_TTL",
    "DEFAULT_SKEW",
    "Clock",
    "InvalidClaims",
    "InvalidSignature",
    "KeyRing",
    "MalformedToken",
    "ManualClock",
    "RefreshReused",
    "RevocationList",
    "Session",
    "SessionRevoked",
    "SessionStore",
    "SweepReport",
    "TokenExpired",
    "TokenNotYetValid",
    "TokenError",
    "TokenPair",
    "TokenService",
    "UnknownKey",
    "UnknownSession",
    "WrongTokenType",
    "canonical_json",
    "new_jti",
    "new_sid",
    "sign_payload",
    "split_token",
    "verify_token",
]

__version__ = "0.4.0"
