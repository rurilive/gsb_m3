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
  revoke.py   RevocationList, per-session tombstones, O(1) lookup
  session.py  TokenService: access/refresh pairs, rotation and sweep
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

## Access and refresh tokens

`TokenService` closes that gap. `issue` opens a session and returns a
pair: a short-lived access token and a long-lived refresh token.
`verify_access` checks signature, token type and expiry window and then
confirms the session is still live and not revoked. Every state lookup is
a dict hit keyed by session id, so verification stays at the same cost
whether the registry holds ten or a hundred thousand sessions.

```python
from tokengate import KeyRing, ManualClock, TokenService

service = TokenService(
    KeyRing({"k1": "secret"}),
    ManualClock(),
    access_ttl=15 * 60,     # access token lifetime
    refresh_ttl=14 * 86400, # refresh token lifetime
    skew=30,                # tolerated clock difference, either direction
)

pair = service.issue({"sub": "u-17"})
service.verify_access(pair.access_token)   # payload dict

rotated = service.refresh(pair.refresh_token)   # brand new pair
service.refresh(pair.refresh_token)
# -> RefreshReused: the old string is dead, and replaying it revokes
#    the whole session (refresh token theft handling)

service.revoke_session(rotated.sid)
service.verify_access(rotated.access_token)     # -> SessionRevoked
```

Replay rules:

* Refreshing rotates both tokens; only the newest refresh token works.
* Presenting an old refresh token raises `RefreshReused` and revokes the
  session, so a thief racing the legitimate client cannot win silently.
* `revoke_session` is idempotent and kills tokens already issued.
* Presenting an access token to `refresh` (or vice versa) raises
  `WrongTokenType`.
* `TokenExpired` / `TokenNotYetValid` mark tokens outside the
  `skew`-widened window; `skew=0` enforces the exact boundary.

`RevocationList` records tombstones by session id (`is_revoked` is a
constant-time dict hit). Tombstones carry a keep-until bound derived from
the refresh lifetime, after which they are safe to forget.

## Sweep

`sweep` removes sessions whose refresh token is past the skew window and
tombstones whose bound has elapsed. Nothing that could still verify is
collected, and under steady issue/revoke/refresh churn the tables stay
bounded:

```python
report = service.sweep()
# SweepReport(sessions_removed, sessions_remaining,
#             revocations_removed, revocations_remaining)
```

All service operations are guarded by one lock, so many threads racing
to refresh the same session produce exactly one successful rotation; a
revocation racing a refresh has a single committed outcome and every
token of the session is refused afterwards.

## Running

```
python3 demo.py                       # guided tour, no arguments
python3 -m unittest discover -s tests # test suite
```

`tests/test_diff_naive.py` replays hundreds of randomized histories
against a naive full-table-scan reference implementation;
`tests/test_perf_access.py` benchmarks `verify_access` at 100k sessions;
`tests/test_concurrency.py`, `tests/test_sweep.py`, `tests/test_session.py`
and `tests/test_revoke.py` cover races, reclamation and token semantics.
