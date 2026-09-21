"""tokengate: HMAC signed tokens and a tiny in-memory session registry.

Public surface:

    KeyRing              secrets addressed by key id
    sign_payload         payload dict -> token string
    verify_token         token string -> payload dict, or raises TokenError
    SessionStore         live session registry
    Clock, ManualClock   injectable time sources
"""

from tokengate.clock import Clock, ManualClock
from tokengate.errors import (
    InvalidSignature,
    MalformedToken,
    TokenError,
    UnknownKey,
    UnknownSession,
)
from tokengate.keys import KeyRing
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
    "Clock",
    "InvalidSignature",
    "KeyRing",
    "MalformedToken",
    "ManualClock",
    "Session",
    "SessionStore",
    "TokenError",
    "UnknownKey",
    "UnknownSession",
    "canonical_json",
    "new_sid",
    "sign_payload",
    "split_token",
    "verify_token",
]

__version__ = "0.3.0"
