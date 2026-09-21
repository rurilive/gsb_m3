"""Signed tokens: base64url(header).base64url(payload).base64url(hmac).

The payload is an opaque dict, returned to the caller exactly as it was
signed. Nothing in here interprets payload keys such as exp or sid.
"""

import base64
import hashlib
import hmac
import json

from tokengate.errors import InvalidSignature, MalformedToken
from tokengate.keys import KeyRing

ALGORITHM = "HS256"
FORMAT_VERSION = 1
DEFAULT_KID = "k1"


def b64u_encode(raw):
    """URL safe base64 without trailing padding."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64u_decode(text):
    """Reverse of b64u_encode; raises MalformedToken on bad input."""
    if not isinstance(text, str):
        raise MalformedToken("token segments must be text")
    pad = "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(text + pad)
    except (ValueError, TypeError):
        raise MalformedToken("segment is not valid base64url")


def canonical_json(obj):
    """Deterministic bytes for a JSON-able object.

    Keys sorted, no incidental whitespace, non-ASCII kept readable. Both
    sides of a signature must agree on these bytes, so this helper is the
    one place the encoding is defined.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _load_segment(text, what):
    raw = b64u_decode(text)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise MalformedToken("%s is not valid JSON" % (what,))
    if not isinstance(value, dict):
        raise MalformedToken("%s must be a JSON object" % (what,))
    return value


def sign_payload(payload, keyring, kid=DEFAULT_KID):
    """Sign ``payload`` and return the token string.

    ``keyring`` is a KeyRing (or anything exposing the same ``secret``
    method); ``kid`` picks the secret to use.
    """
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    secret = _secret_of(keyring, kid)
    header = {"alg": ALGORITHM, "kid": kid, "v": FORMAT_VERSION}
    signing_input = "%s.%s" % (b64u_encode(canonical_json(header)),
                               b64u_encode(canonical_json(payload)))
    digest = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return "%s.%s" % (signing_input, b64u_encode(digest))


def split_token(token):
    """Return (header, payload, signature_b64) after structural checks."""
    if not isinstance(token, str):
        raise MalformedToken("token must be a string")
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise MalformedToken("token must have three non-empty segments")
    header = _load_segment(parts[0], "header")
    payload = _load_segment(parts[1], "payload")
    return header, payload, parts[2]


def verify_token(token, keyring):
    """Check structure, header and signature; return the payload dict.

    Raises MalformedToken, UnknownKey or InvalidSignature. The returned
    dict is a fresh copy, safe for the caller to mutate.
    """
    header, payload, signature_b64 = split_token(token)
    if header.get("alg") != ALGORITHM:
        raise MalformedToken("unsupported alg %r" % (header.get("alg"),))
    if header.get("v") != FORMAT_VERSION:
        raise MalformedToken("unsupported token version %r" % (header.get("v"),))
    kid = header.get("kid")
    secret = _secret_of(keyring, kid)
    signing_input = token.rsplit(".", 1)[0]
    expected = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    given = b64u_decode(signature_b64)
    if not hmac.compare_digest(expected, given):
        raise InvalidSignature("signature does not match")
    return dict(payload)


def _secret_of(keyring, kid):
    if isinstance(keyring, KeyRing):
        return keyring.secret(kid)
    if hasattr(keyring, "secret"):
        return keyring.secret(kid)
    if isinstance(keyring, (bytes, str)) and kid == DEFAULT_KID:
        return keyring.encode("utf-8") if isinstance(keyring, str) else keyring
    raise TypeError("pass a KeyRing or a keyring-like object with a secret() method")
