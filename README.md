# tokengate

Small, dependency-free library for HMAC signed tokens and an in-memory
session registry. Pure standard library, Python 3.8+.

## Layout

```
tokengate/
  errors.py   exception types (all rejections derive from TokenError)
  clock.py    Clock and ManualClock, injected wherever time is needed
  keys.py     KeyRing, secrets addressed by key id for rotation
  token.py    sign_payload / verify_token, base64url header.payload.signature
  store.py    SessionStore, the registry of live sessions
tests/        unittest suite
demo.py       guided tour, run it directly
```

## Token format

`base64url(header).base64url(payload).base64url(hmac-sha256)` where the
MAC covers the first two segments verbatim. The header carries `alg`,
`kid` and `v`. The payload is an opaque dict: `verify_token` hands it back
exactly as signed and attaches no meaning to any key.

Signing always encodes through `tokengate.token.canonical_json`, so a
given payload dict has exactly one token string regardless of key order.

## Usage

```python
from tokengate import KeyRing, sign_payload, verify_token

ring = KeyRing({"k1": "secret"})
token = sign_payload({"sub": "u-17"}, ring)
verify_token(token, ring)          # -> {"sub": "u-17"}
```

Every rejection (bad shape, unknown kid, bad signature) raises a subclass
of `TokenError`; nothing else is raised for a bad token.

## Sessions

```python
from tokengate import ManualClock, SessionStore

store = SessionStore(ManualClock())
session = store.open({"sub": "u-17"})   # sid generated, record has opened_at
store.get(session.sid)                  # Session or None
store.close(session.sid)                # True if removed, idempotent
```

`close` removes the record from the registry. Token strings are signed
material and have no link back to the registry, so the store on its own
says nothing about tokens that were handed out earlier.

## Running

```
python3 demo.py                       # guided tour, no arguments
python3 -m unittest discover -s tests # test suite
```
