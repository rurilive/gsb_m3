"""QuorumLease 现有行为的锁定测试。"""

import unittest

from quolease.core import QuorumLease


class TestMembership(unittest.TestCase):
    def setUp(self):
        self.voters = {n: True for n in "abcde"}
        self.q = QuorumLease(self.voters, clock=lambda: 1000.0)

    def test_members_sorted(self):
        self.assertEqual(self.q.members(), ["a", "b", "c", "d", "e"])

    def test_members_reads_injected_table(self):
        self.voters["f"] = True
        self.assertEqual(self.q.members(), ["a", "b", "c", "d", "e", "f"])

    def test_alive_members_tracks_table(self):
        self.voters["c"] = False
        self.assertEqual(self.q.alive_members(), ["a", "b", "d", "e"])

    def test_quorum_size_is_majority(self):
        self.assertEqual(self.q.quorum_size(), 3)

    def test_quorum_size_for_even_members(self):
        q = QuorumLease({n: True for n in "abcd"}, clock=lambda: 0.0)
        self.assertEqual(q.quorum_size(), 3)

    def test_has_quorum_false_when_minority(self):
        for n in "cde":
            self.voters[n] = False
        self.assertFalse(self.q.has_quorum())

    def test_has_quorum_true_with_exactly_majority(self):
        for n in "de":
            self.voters[n] = False
        self.assertTrue(self.q.has_quorum())


class TestElection(unittest.TestCase):
    def setUp(self):
        self.voters = {n: True for n in "abcde"}
        self.now = [1000.0]
        self.q = QuorumLease(
            self.voters, clock=lambda: self.now[0], lease_seconds=10.0
        )

    def test_elect_picks_smallest_alive(self):
        self.assertEqual(self.q.elect(), "a")
        self.assertEqual(self.q.leader(), "a")

    def test_elect_skips_down_members(self):
        self.voters["a"] = False
        self.assertEqual(self.q.elect(), "b")

    def test_elect_without_quorum_returns_none(self):
        for n in "cde":
            self.voters[n] = False
        self.assertIsNone(self.q.elect())

    def test_elect_without_quorum_keeps_existing_leader(self):
        self.q.elect()
        for n in "cde":
            self.voters[n] = False
        self.assertIsNone(self.q.elect())
        self.assertEqual(self.q.leader(), "a")

    def test_elect_bumps_term(self):
        self.assertEqual(self.q.term(), 0)
        self.q.elect()
        self.q.elect()
        self.assertEqual(self.q.term(), 2)


class TestRenew(unittest.TestCase):
    def setUp(self):
        self.voters = {n: True for n in "abcde"}
        self.now = [1000.0]
        self.q = QuorumLease(
            self.voters, clock=lambda: self.now[0], lease_seconds=10.0
        )
        self.q.elect()

    def test_leader_can_renew(self):
        self.assertTrue(self.q.renew("a"))
        self.assertEqual(self.q.lease_expires_at(), 1010.0)

    def test_non_leader_cannot_renew(self):
        self.assertFalse(self.q.renew("b"))
        self.assertIsNone(self.q.lease_expires_at())

    def test_no_lease_before_first_renew(self):
        self.assertIsNone(self.q.lease_expires_at())

    def test_renew_uses_injected_clock(self):
        self.q.renew("a")
        self.now[0] = 1005.0
        self.q.renew("a")
        self.assertEqual(self.q.lease_expires_at(), 1015.0)

    def test_invalid_lease_seconds_raises(self):
        with self.assertRaises(ValueError):
            QuorumLease(self.voters, lease_seconds=0)


if __name__ == "__main__":
    unittest.main()
