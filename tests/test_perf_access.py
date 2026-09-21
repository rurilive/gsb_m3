import statistics
import timeit
import unittest

from tokengate import KeyRing, ManualClock, RevocationList, SessionStore, TokenService


def build_service(n_sessions, n_revoked):
    clock = ManualClock(1_700_000_000.0)
    ring = KeyRing({"k1": "perf-secret"})
    store = SessionStore(clock)
    revocations = RevocationList(clock)
    svc = TokenService(ring, clock, store=store, revocations=revocations,
                       access_ttl=3600, refresh_ttl=86400, skew=5)
    target = None
    for i in range(n_sessions):
        pair = svc.issue({"sub": "u-%d" % i})
        if i == n_sessions // 2:
            target = pair
    for i in range(n_revoked):
        pair = svc.issue({"sub": "gone-%d" % i})
        svc.revoke_session(pair.sid)
    return svc, target


def median_verify(svc, token, number=2000, repeat=5):
    timer = timeit.Timer(lambda: svc.verify_access(token))
    samples = [t / number for t in timer.repeat(repeat=repeat, number=number)]
    return statistics.median(samples)


class VerifyAccessPerformanceTests(unittest.TestCase):
    def test_constant_time_independent_of_table_size(self):
        small, token_small = build_service(100, 100)
        big, token_big = build_service(100_000, 10_000)

        # Warm up so import/jit-ish effects do not skew the first read.
        small.verify_access(token_small.access_token)
        big.verify_access(token_big.access_token)

        median_small = median_verify(small, token_small.access_token)
        median_big = median_verify(big, token_big.access_token)

        print("\nverify_access median: "
              "200 sessions=%.2f us, 110k rows=%.2f us"
              % (median_small * 1e6, median_big * 1e6))

        # Hundred-microsecond class at 100k sessions...
        self.assertLess(median_big, 200e-6)
        # ...and no meaningful growth with the table length.
        self.assertLess(median_big, median_small * 2.0 + 5e-6)


if __name__ == "__main__":
    unittest.main()
