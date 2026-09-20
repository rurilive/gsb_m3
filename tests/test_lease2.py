"""租约多数派协商、退位与代数的新行为测试，时钟全部注入。"""

import unittest

from quolease.core import QuorumLease


class LeaseCase(unittest.TestCase):
    def setUp(self):
        self.voters = {n: True for n in "abc"}
        self.now = [1000.0]
        self.q = QuorumLease(
            self.voters, clock=lambda: self.now[0], lease_seconds=10.0
        )
        self.q.elect()  # leader = "a"，quorum = 2


class TestNegotiatedRenew(LeaseCase):
    def test_accepts_shortest_receipt(self):
        ok = self.q.renew("a", {"a": 1010.0, "b": 1006.0, "c": 1008.0})
        self.assertTrue(ok)
        self.assertEqual(self.q.lease_expires_at(), 1006.0)

    def test_exact_quorum_of_receipts_is_enough(self):
        self.assertTrue(self.q.renew("a", {"a": 1010.0, "b": 1009.0}))
        self.assertEqual(self.q.lease_expires_at(), 1009.0)

    def test_rejects_when_receipts_below_quorum(self):
        self.assertFalse(self.q.renew("a", {"a": 1010.0}))
        self.assertIsNone(self.q.lease_expires_at())

    def test_down_member_receipts_dont_count(self):
        self.voters["c"] = False
        self.assertFalse(self.q.renew("a", {"a": 1010.0, "c": 1010.0}))
        self.assertTrue(self.q.renew("a", {"a": 1010.0, "b": 1010.0}))

    def test_unknown_member_receipts_ignored(self):
        self.assertFalse(self.q.renew("a", {"a": 1010.0, "zz": 1001.0}))
        self.assertIsNone(self.q.lease_expires_at())

    def test_non_leader_cannot_negotiate(self):
        self.assertFalse(self.q.renew("b", {"a": 1010.0, "b": 1010.0}))
        self.assertIsNone(self.q.lease_expires_at())

    def test_local_renew_refused_without_quorum(self):
        self.voters["b"] = False
        self.voters["c"] = False
        self.assertFalse(self.q.renew("a"))
        self.assertIsNone(self.q.lease_expires_at())


class TestMembershipRecompute(LeaseCase):
    def test_growth_raises_quorum_for_renew(self):
        self.voters["d"] = True
        self.voters["e"] = True  # 5 成员，多数派 3
        self.assertEqual(self.q.quorum_size(), 3)
        self.assertFalse(self.q.renew("a", {"a": 1010.0, "b": 1010.0}))
        ok = self.q.renew("a", {"a": 1010.0, "b": 1010.0, "d": 1005.0})
        self.assertTrue(ok)
        self.assertEqual(self.q.lease_expires_at(), 1005.0)

    def test_shrink_lowers_quorum_for_renew(self):
        del self.voters["b"]
        del self.voters["c"]  # 只剩 a，多数派 1
        self.assertEqual(self.q.quorum_size(), 1)
        self.assertTrue(self.q.renew("a", {"a": 1009.0}))
        self.assertEqual(self.q.lease_expires_at(), 1009.0)


class TestAbdicate(LeaseCase):
    def test_abdicate_clears_leader_and_lease(self):
        self.q.renew("a", {"a": 1010.0, "b": 1010.0})
        self.assertTrue(self.q.abdicate())
        self.assertIsNone(self.q.leader())
        self.assertIsNone(self.q.lease_expires_at())

    def test_abdicate_without_leader_is_noop(self):
        q = QuorumLease({"a": True}, clock=lambda: 0.0)
        self.assertFalse(q.abdicate())
        self.assertEqual(q.generation(), 0)

    def test_no_write_permit_after_abdicate(self):
        self.q.renew("a", {"a": 1010.0, "b": 1010.0})
        gen = self.q.generation()
        self.q.abdicate()
        self.assertFalse(self.q.write_permit("a", gen))


class TestGeneration(LeaseCase):
    def test_generation_bumps_on_leader_change(self):
        gen = self.q.generation()
        self.q.elect()  # 仍是 a，不算换主
        self.assertEqual(self.q.generation(), gen)
        self.voters["a"] = False
        self.assertEqual(self.q.elect(), "b")
        self.assertEqual(self.q.generation(), gen + 1)

    def test_generation_bumps_on_abdicate(self):
        gen = self.q.generation()
        self.q.abdicate()
        self.assertEqual(self.q.generation(), gen + 1)

    def test_leader_change_drops_old_lease(self):
        self.q.renew("a", {"a": 1010.0, "b": 1010.0})
        self.voters["a"] = False
        self.q.elect()
        self.assertIsNone(self.q.lease_expires_at())


class TestWritePermit(LeaseCase):
    def test_permit_requires_leader_lease_quorum_and_generation(self):
        self.q.renew("a", {"a": 1010.0, "b": 1010.0})
        gen = self.q.generation()
        self.assertTrue(self.q.write_permit("a", gen))
        self.assertFalse(self.q.write_permit("b", gen))  # 非 leader
        self.assertFalse(self.q.write_permit("a", gen + 1))  # 旧/错代数

    def test_permit_expires_with_lease(self):
        self.q.renew("a", {"a": 1010.0, "b": 1010.0})
        gen = self.q.generation()
        self.now[0] = 1009.9
        self.assertTrue(self.q.write_permit("a", gen))
        self.now[0] = 1010.0
        self.assertFalse(self.q.write_permit("a", gen))

    def test_permit_refused_without_quorum(self):
        self.q.renew("a", {"a": 1010.0, "b": 1010.0})
        gen = self.q.generation()
        self.voters["b"] = False
        self.voters["c"] = False
        self.assertFalse(self.q.write_permit("a", gen))


class TestPartitionHeal(LeaseCase):
    def test_resync_realigns_generation_after_partition(self):
        self.q.renew("a", {"a": 1010.0, "b": 1010.0})
        stale = self.q.generation()
        self.assertTrue(self.q.write_permit("a", stale))

        # 分区：a 被隔离成少数派，续不上租，必须退位
        self.voters["b"] = False
        self.voters["c"] = False
        self.assertFalse(self.q.renew("a"))
        self.assertFalse(self.q.write_permit("a", stale))
        self.assertTrue(self.q.abdicate())

        # 分区恢复，重新选主；归来的节点用 resync 对齐代数
        self.voters["b"] = True
        self.voters["c"] = True
        self.assertEqual(self.q.elect(), "a")
        current = self.q.resync()
        self.assertNotEqual(current, stale)

        self.q.renew("a", {"a": 1010.0, "b": 1010.0})
        self.assertFalse(self.q.write_permit("a", stale))  # 旧代数发不出
        self.assertTrue(self.q.write_permit("a", current))


if __name__ == "__main__":
    unittest.main()
