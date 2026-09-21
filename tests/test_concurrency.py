import threading
import unittest

from tokengate import KeyRing, ManualClock, RefreshReused, SessionRevoked, TokenService


def make_service():
    return TokenService(KeyRing({"k1": "shared-secret"}), ManualClock(10_000.0),
                        access_ttl=60, refresh_ttl=600, skew=5)


class RefreshRaceTests(unittest.TestCase):
    def test_only_one_refresh_of_the_same_token_wins(self):
        for _ in range(25):
            svc = make_service()
            pair = svc.issue()
            winners = []
            errors = []
            barrier = threading.Barrier(8)

            def worker():
                barrier.wait()
                try:
                    winners.append(svc.refresh(pair.refresh_token))
                except Exception as exc:  # noqa: BLE001 - asserted below
                    errors.append(type(exc))

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(len(winners), 1, errors)
            self.assertEqual(len(errors), 7)
            # The seven losers reused a now-stale token: the session is
            # revoked exactly once and every later access is refused.
            self.assertTrue(set(errors) <= {RefreshReused, SessionRevoked})
            with self.assertRaises(SessionRevoked):
                svc.verify_access(winners[0].access_token)

    def test_chain_race_against_the_winner_still_single_winner(self):
        # Even when a loser retries with the winner's new token, at most
        # one refresh in the burst can claim it.
        for _ in range(10):
            svc = make_service()
            pair = svc.issue()
            first = svc.refresh(pair.refresh_token)
            winners = []
            errors = []
            barrier = threading.Barrier(6)

            def worker():
                barrier.wait()
                try:
                    winners.append(svc.refresh(first.refresh_token))
                except Exception as exc:
                    errors.append(type(exc))

            threads = [threading.Thread(target=worker) for _ in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(len(winners), 1, errors)
            self.assertEqual(len(errors), 5)


class RevokeRefreshRaceTests(unittest.TestCase):
    def _assert_final_state_dead(self, svc, sid):
        self.assertNotIn(sid, svc.store)
        self.assertIn(sid, svc.revocations)
        self.assertEqual(len(svc.revocations), 1)

    def test_refresh_then_revoke_ordering(self):
        # Refresh reaches the mint point first; revoke waits for it,
        # then closes the freshly rotated session. Exactly one winner.
        svc = make_service()
        pair = svc.issue()
        rotated_holder = {}
        can_revoke = threading.Event()

        def on_rotate():
            can_revoke.set()

        svc.set_test_hooks(on_rotate=on_rotate)

        def do_refresh():
            rotated_holder["pair"] = svc.refresh(pair.refresh_token)

        refresh_thread = threading.Thread(target=do_refresh)
        refresh_thread.start()
        self.assertTrue(can_revoke.wait(2.0))
        # Give the refresh thread no chance to release the lock early:
        # revoke now blocks until the rotation fully commits.
        self.assertTrue(svc.revoke_session(pair.sid))
        refresh_thread.join(2.0)
        self.assertFalse(refresh_thread.is_alive())

        rotated = rotated_holder["pair"]
        self._assert_final_state_dead(svc, pair.sid)
        with self.assertRaises(SessionRevoked):
            svc.verify_access(pair.access_token)
        with self.assertRaises(SessionRevoked):
            svc.verify_access(rotated.access_token)
        with self.assertRaises(SessionRevoked):
            svc.refresh(rotated.refresh_token)
        self.assertFalse(svc.revoke_session(pair.sid))

    def test_revoke_then_refresh_ordering(self):
        # Revoke reaches its commit point while refresh is queued on
        # the lock; refresh must then observe the tombstone.
        svc = make_service()
        pair = svc.issue()
        can_finish_revoke = threading.Event()
        refresh_started = threading.Event()

        def on_revoke():
            refresh_started.set()
            can_finish_revoke.wait(2.0)

        svc.set_test_hooks(on_revoke=on_revoke)

        def do_revoke():
            svc.revoke_session(pair.sid)

        revoke_thread = threading.Thread(target=do_revoke)
        revoke_thread.start()
        # Wait until revoke is inside its locked section, then launch
        # the refresh (it blocks on the lock), and finally let revoke
        # commit.
        self.assertTrue(refresh_started.wait(2.0))
        result = {}

        def do_refresh():
            result["error"] = None
            try:
                svc.refresh(pair.refresh_token)
            except Exception as exc:  # noqa: BLE001
                result["error"] = type(exc)

        refresh_thread = threading.Thread(target=do_refresh)
        refresh_thread.start()
        can_finish_revoke.set()
        revoke_thread.join(2.0)
        refresh_thread.join(2.0)

        self.assertIs(result["error"], SessionRevoked)
        self._assert_final_state_dead(svc, pair.sid)

    def test_natural_race_always_ends_revoked(self):
        # Hammer without hooks: outcome ordering may vary, but the final
        # state and the "exactly one commit" rule never do.
        for _ in range(40):
            svc = make_service()
            pair = svc.issue()
            barrier = threading.Barrier(2)

            def do_refresh():
                barrier.wait()
                try:
                    svc.refresh(pair.refresh_token)
                except Exception:
                    pass

            def do_revoke():
                barrier.wait()
                svc.revoke_session(pair.sid)

            threads = [threading.Thread(target=do_refresh),
                       threading.Thread(target=do_revoke)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self._assert_final_state_dead(svc, pair.sid)
            with self.assertRaises(SessionRevoked):
                svc.verify_access(pair.access_token)

    def test_two_revokes_and_refresh_leave_one_tombstone(self):
        for _ in range(20):
            svc = make_service()
            pair = svc.issue()
            revoke_results = []
            barrier = threading.Barrier(3)

            def refresh_worker():
                barrier.wait()
                try:
                    svc.refresh(pair.refresh_token)
                except Exception:
                    pass

            def revoke_worker():
                barrier.wait()
                revoke_results.append(svc.revoke_session(pair.sid))

            threads = [
                threading.Thread(target=refresh_worker),
                threading.Thread(target=revoke_worker),
                threading.Thread(target=revoke_worker),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(sorted(revoke_results), [False, True])
            self.assertEqual(len(svc.revocations), 1)

    def test_revoke_under_refresh_storm_commits_at_most_once(self):
        for _ in range(10):
            svc = make_service()
            pair = svc.issue()
            revoke_results = []
            barrier = threading.Barrier(9)

            def refresh_worker():
                barrier.wait()
                try:
                    svc.refresh(pair.refresh_token)
                except Exception:
                    pass

            def revoke_worker():
                barrier.wait()
                revoke_results.append(svc.revoke_session(pair.sid))

            threads = [threading.Thread(target=refresh_worker) for _ in range(8)]
            threads.append(threading.Thread(target=revoke_worker))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(revoke_results.count(True), 1)
            self.assertNotIn(pair.sid, svc.store)


if __name__ == "__main__":
    unittest.main()
