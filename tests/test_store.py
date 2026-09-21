import unittest

from tokengate import ManualClock, SessionStore, UnknownSession, new_sid


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.clock = ManualClock(1_700_000_000.0)
        self.store = SessionStore(self.clock)

    def test_open_registers_a_session(self):
        session = self.store.open({"sub": "u-1", "role": "admin"})
        self.assertEqual(session.claims, {"sub": "u-1", "role": "admin"})
        self.assertEqual(session.opened_at, 1_700_000_000.0)
        self.assertEqual(len(self.store), 1)
        self.assertIn(session.sid, self.store)

    def test_opened_at_follows_the_clock(self):
        self.clock.advance(120)
        session = self.store.open()
        self.assertEqual(session.opened_at, 1_700_000_120.0)

    def test_open_without_claims(self):
        self.assertEqual(self.store.open().claims, {})

    def test_generated_ids_are_unique(self):
        sids = {self.store.open().sid for _ in range(50)}
        self.assertEqual(len(sids), 50)

    def test_explicit_sid_must_be_free(self):
        self.store.open(sid="fixed")
        with self.assertRaises(ValueError):
            self.store.open(sid="fixed")

    def test_get_unknown_returns_none(self):
        self.assertIsNone(self.store.get("ghost"))

    def test_require_unknown_raises(self):
        with self.assertRaises(UnknownSession):
            self.store.require("ghost")

    def test_require_returns_the_session(self):
        session = self.store.open(sid="a")
        self.assertIs(self.store.require("a"), session)

    def test_close_is_idempotent(self):
        session = self.store.open()
        self.assertTrue(self.store.close(session.sid))
        self.assertFalse(self.store.close(session.sid))
        self.assertIsNone(self.store.get(session.sid))
        self.assertEqual(len(self.store), 0)

    def test_sids_are_sorted(self):
        for sid in ("b", "a", "c"):
            self.store.open(sid=sid)
        self.assertEqual(self.store.sids(), ["a", "b", "c"])
        self.assertEqual(list(self.store), ["a", "b", "c"])

    def test_claims_are_copied_on_the_way_in(self):
        source = {"sub": "u-1"}
        session = self.store.open(source)
        source["sub"] = "u-2"
        self.assertEqual(session.claims["sub"], "u-1")

    def test_info_snapshot_is_detached(self):
        session = self.store.open({"sub": "u-1"})
        info = session.info()
        info["claims"]["sub"] = "u-9"
        self.assertEqual(session.claims["sub"], "u-1")

    def test_new_sid_shape(self):
        sid = new_sid()
        self.assertIsInstance(sid, str)
        self.assertGreaterEqual(len(sid), 16)
        self.assertNotEqual(sid, new_sid())


if __name__ == "__main__":
    unittest.main()
