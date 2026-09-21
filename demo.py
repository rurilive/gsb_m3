"""Walk through the tokengate basics on a fake clock."""

from tokengate import (
    Clock,
    InvalidSignature,
    KeyRing,
    ManualClock,
    SessionStore,
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

    section("6. real wall clock")
    print("Clock().now():", Clock().now())

    print("\ndone")


if __name__ == "__main__":
    main()
