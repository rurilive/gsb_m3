"""租约多数派协商、退位与代数的行为测试。"""

import unittest

from quolease.core import QuorumLease


class LeaseCase(unittest.TestCase):
    def setUp(self):
        self.voters = {n: True for n in "abcde"}
        self.now = [1000.0]
        self.q = QuorumLease(
            self.voters, clock=lambda: self.now[0], lease_seconds=10.0
        )
        self.q.elect()  # leader = "a", generation = 1


class TestNegotiatedRenew(LeaseCase):
    def test_renew_takes_shortest_ack(self):
        acks = {"a": 1010.0, "b": 1006.0, "c": 1009.0}
        self.assertTrue(self.q.renew("a", acks))
        self.assertEqual(self.q.lease_expires_at(), 1006.0)

    def test_renew_rejects_when_acks_lack_quorum(self):
        self.assertFalse(self.q.renew("a", {"a": 1010.0, "b": 1010.0}))
        self.assertIsNone(self.q.lease_expires_at())

    def test_renew_ignores_acks_from_dead_members(self):
        self.voters["c"] = False
        acks = {"a": 1010.0, "b": 1010.0, "c": 1001.0}
        self.assertFalse(self.q.renew("a", acks))  # 在线回执只有 2 票
        self.assertIsNone(self.q.lease_expires_at())

    def test_renew_rejects_without_quorum(self):
        for n in "cde":
            self.voters[n] = False
        self.assertFalse(self.q.renew("a"))
        self.assertIsNone(self.q.lease_expires_at())

    def test_membership_growth_recomputes_quorum(self):
        acks3 = {"a": 1010.0, "b": 1010.0, "c": 1010.0}
        self.assertTrue(self.q.renew("a", acks3))
        self.voters["f"] = True
        self.voters["g"] = True  # 7 成员，多数派变 4
        self.assertEqual(self.q.quorum_size(), 4)
        self.assertFalse(self.q.renew("a", acks3))
        self.assertEqual(self.q.lease_expires_at(), 1010.0)  # 旧租约不动
        acks4 = {"a": 1020.0, "b": 1018.0, "c": 1020.0, "d": 1019.0}
        self.assertTrue(self.q.renew("a", acks4))
        self.assertEqual(self.q.lease_expires_at(), 1018.0)

    def test_membership_shrink_recomputes_quorum(self):
        for n in "de":
            del self.voters[n]  # 缩容到 3 成员，多数派变 2
        self.assertEqual(self.q.quorum_size(), 2)
        self.assertTrue(self.q.renew("a", {"a": 1007.0, "b": 1009.0}))
        self.assertEqual(self.q.lease_expires_at(), 1007.0)


class TestAbdicate(LeaseCase):
    def test_abdicate_clears_leader_and_lease(self):
        self.q.renew("a")
        self.q.abdicate()
        self.assertIsNone(self.q.leader())
        self.assertIsNone(self.q.lease_expires_at())

    def test_abdicate_bumps_generation(self):
        gen = self.q.generation()
        self.q.abdicate()
        self.assertEqual(self.q.generation(), gen + 1)

    def test_no_write_permit_after_abdicate(self):
        self.q.renew("a")
        gen = self.q.generation()
        self.assertTrue(self.q.write_permit(gen))
        self.q.abdicate()
        self.assertFalse(self.q.write_permit(gen))


class TestGenerationAndPermit(LeaseCase):
    def test_generation_bumps_on_leader_change(self):
        self.assertEqual(self.q.generation(), 1)
        self.q.elect()  # 同一人连任，不换主
        self.assertEqual(self.q.generation(), 1)
        self.voters["a"] = False
        self.q.elect()  # 换主为 "b"
        self.assertEqual(self.q.generation(), 2)

    def test_write_permit_requires_live_lease(self):
        gen = self.q.generation()
        self.assertFalse(self.q.write_permit(gen))  # 还没有租约
        self.q.renew("a")
        self.assertTrue(self.q.write_permit(gen))
        self.now[0] = 1009.5
        self.assertTrue(self.q.write_permit(gen))
        self.now[0] = 1010.0  # 到期时刻即失效
        self.assertFalse(self.q.write_permit(gen))

    def test_write_permit_rejects_stale_generation(self):
        self.q.renew("a")
        stale = self.q.generation()
        self.q.abdicate()
        self.q.elect()
        self.q.renew("a")
        self.assertFalse(self.q.write_permit(stale))
        self.assertTrue(self.q.write_permit(self.q.generation()))

    def test_write_permit_rejects_without_quorum(self):
        self.q.renew("a")
        gen = self.q.generation()
        for n in "cde":
            self.voters[n] = False
        self.assertFalse(self.q.write_permit(gen))

    def test_write_permit_rejects_dead_leader(self):
        self.q.renew("a")
        gen = self.q.generation()
        self.voters["a"] = False
        self.assertFalse(self.q.write_permit(gen))


class TestResync(LeaseCase):
    def test_resync_aligns_returning_node(self):
        # 分区归来的节点：本地代数停在旧值
        lagging = QuorumLease(
            self.voters, clock=lambda: self.now[0], lease_seconds=10.0
        )
        lagging.elect()
        lagging.renew("a")
        stale = lagging.generation()
        # 集群侧经历退位与换主，代数已前进
        self.q.abdicate()
        self.voters["a"] = False
        self.q.elect()
        self.assertGreater(self.q.generation(), stale)
        lagging.resync(self.q.generation())
        self.assertEqual(lagging.generation(), self.q.generation())
        # 旧代数发不出写许可
        self.assertFalse(lagging.write_permit(stale))


if __name__ == "__main__":
    unittest.main()
