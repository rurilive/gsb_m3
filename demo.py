"""Walk through the tokengate basics on a fake clock."""

from tokengate import (
    Clock,
    InvalidSignature,
    KeyRing,
    ManualClock,
    RefreshReused,
    SessionRevoked,
    SessionStore,
    TokenExpired,
    TokenService,
    TokenError,
    sign_payload,
    verify_token,
)
from tokengate.token import split_token

LINE = "-" * 58


def section(title):
    print("\n%s\n%s" % (title, LINE))


def main():
    ring = KeyRing({"k1": "demo-secret-one", "k2": "demo-secret-two"})
    clock = ManualClock(1_700_000_000.0)

    section("1. sign a payload")
    token = sign_payload({"sub": "u-17", "role": "admin"}, ring)
    header, payload, signature = split_token(token)
    print("header   :", header)
    print("payload  :", payload)
    print("token    : %s..." % token[:64])

    section("2. verify it")
    print("verdict  :", verify_token(token, ring))

    section("3. a tampered copy is refused")
    head, body, sig = token.split(".")
    flipped = "A" if sig[0] != "A" else "B"
    forged = ".".join([head, body, flipped + sig[1:]])
    try:
        verify_token(forged, ring)
    except TokenError as exc:
        print("refused  : %s: %s" % (type(exc).__name__, exc))
    else:
        print("refused  : no, which is a bug")

    section("4. key rotation")
    rotated = sign_payload({"sub": "u-17"}, ring, kid="k2")
    ring.drop("k1")
    print("after dropping k1, old token: ", end="")
    try:
        verify_token(token, ring)
    except TokenError as exc:
        print("refused (%s)" % type(exc).__name__)
    print("token signed with k2 still verifies:", verify_token(rotated, ring))

    section("5. sessions on a manual clock")
    store = SessionStore(clock)
    session = store.open({"sub": "u-17", "device": "laptop"})
    print("opened   :", session.info(), "at", clock.now())
    clock.advance(300)
    print("clock    :", clock.now())
    print("live     :", store.sids(), "count =", len(store))
    store.close(session.sid)
    print("after close, count =", len(store))
    print("session record gone, but the token string above is still a")
    print("valid signature: stateless tokens outlive the store entry.")

    section("6. issue an access/refresh pair")
    ring.add("k1", "demo-secret-one")  # restore the key section 4 dropped
    service_clock = ManualClock(1_700_000_000.0)
    service = TokenService(
        ring, service_clock, access_ttl=300, refresh_ttl=3600, skew=10)
    pair = service.issue({"sub": "u-17", "device": "laptop"})
    print("sid          :", pair.sid)
    print("access exp   :", pair.access_exp, "(5 minutes)")
    print("refresh exp  :", pair.refresh_exp, "(1 hour)")
    print("access check :", service.verify_access(pair.access_token)["sub"])

    section("7. refresh rotates the pair")
    service_clock.advance(200)
    rotated = service.refresh(pair.refresh_token)
    print("new pair     : tokens differ:",
          rotated.access_token != pair.access_token)
    try:
        service.refresh(pair.refresh_token)
    except TokenError as exc:
        print("old refresh  : %s - session revoked as suspected theft"
              % type(exc).__name__)
    try:
        service.verify_access(rotated.access_token)
    except SessionRevoked:
        print("new access   : SessionRevoked too, the session is dead")

    section("8. logout revokes tokens already handed out")
    pair2 = service.issue({"sub": "u-18"})
    service.revoke_session(pair2.sid)
    try:
        service.verify_access(pair2.access_token)
    except TokenError as exc:
        print("access after revoke :", type(exc).__name__)
    try:
        service.refresh(pair2.refresh_token)
    except TokenError as exc:
        print("refresh after revoke:", type(exc).__name__)

    section("9. clock skew window")
    strict = TokenService(ring, ManualClock(2_000_000_000.0),
                          access_ttl=60, refresh_ttl=600, skew=5)
    p3 = strict.issue()
    strict.clock.advance(64)
    print("4 seconds late, inside skew:",
          end=" ")
    try:
        strict.verify_access(p3.access_token)
        print("accepted")
    except TokenExpired:
        print("refused")
    strict.clock.advance(2)
    try:
        strict.verify_access(p3.access_token)
    except TokenExpired:
        print("past the window            : refused (TokenExpired)")

    section("10. sweep reclaims aged state")
    sweeping = TokenService(ring, ManualClock(3_000_000_000.0),
                            access_ttl=10, refresh_ttl=100, skew=0)
    live = sweeping.issue()
    gone = sweeping.issue()
    sweeping.revoke_session(gone.sid)
    sweeping.clock.advance(1000)
    report = sweeping.sweep()
    print("swept        :", report)
    print("live sessions:", len(sweeping.store),
          " tombstones:", len(sweeping.revocations))

    section("11. real wall clock")
    print("Clock().now():", Clock().now())

    print("\ndone")


if __name__ == "__main__":
    main()
