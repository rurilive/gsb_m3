"""quorkit 线上双主事故的防回归测试。

按事故里的四类现象分组，每条都对着当时的时序重放：

1. 多数派门槛按当前在册成员动态算，扩容/缩容都立刻生效；
2. 活跃判定统一走集群协商的 heartbeat_timeout，本机配置不参与；
3. 任期严格往前，旧任期心跳一律拒绝，且不刷新活跃时间戳；
4. 摘除的成员立刻退出计票，留在表里的旧时间戳不再抬高人数。
"""

import unittest

from quorkit.quorum import MemberTable, Quorum


class FakeClock:
    """手动推进的假时钟。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now


def cluster_of(*nodes):
    return MemberTable(nodes)


class TestDynamicMajority(unittest.TestCase):
    def test_majority_tracks_membership_growth(self):
        cluster = cluster_of("n1", "n2", "n3")
        q = Quorum(cluster, clock=FakeClock(), timeout=10.0)
        self.assertEqual(q.majority(), 2)
        cluster.add("n4")
        cluster.add("n5")
        self.assertEqual(q.majority(), 3)

    def test_majority_tracks_membership_shrink(self):
        cluster = cluster_of("n1", "n2", "n3", "n4", "n5")
        q = Quorum(cluster, clock=FakeClock(), timeout=10.0)
        cluster.remove("n4")
        cluster.remove("n5")
        self.assertEqual(q.majority(), 2)

    def test_stale_quorum_after_expansion_cannot_elect(self):
        # 事故时序：备用节点扩容进来后，老进程还按 3 成员的门槛凑票。
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3")
        q = Quorum(cluster, clock=clock, timeout=10.0)
        cluster.add("n4")
        cluster.add("n5")
        q.heartbeat("n1", 0.0, 1)
        q.heartbeat("n2", 0.0, 1)
        self.assertIsNone(q.elect())
        q.heartbeat("n3", 0.0, 1)
        self.assertEqual(q.elect(), 2)

    def test_shrunk_cluster_uses_new_threshold(self):
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3", "n4", "n5")
        q = Quorum(cluster, clock=clock, timeout=10.0)
        for node in ("n1", "n2", "n3"):
            q.heartbeat(node, 0.0, 0)
        cluster.remove("n4")
        cluster.remove("n5")
        self.assertEqual(q.majority(), 2)
        self.assertEqual(q.elect(), 1)


class TestNegotiatedLiveness(unittest.TestCase):
    def test_active_uses_negotiated_timeout_not_local(self):
        clock = FakeClock()
        q = Quorum(
            cluster_of("n1", "n2", "n3"),
            clock=clock,
            timeout=30.0,
            config={"heartbeat_timeout": 5.0},
        )
        q.heartbeat("n1", 0.0, 1)
        clock.advance(12.0)
        self.assertEqual(q.active(), set())

    def test_nodes_with_divergent_local_timeouts_agree(self):
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3", "n4", "n5")
        node_a = Quorum(cluster, clock=clock, timeout=30.0,
                        config={"heartbeat_timeout": 5.0})
        node_b = Quorum(cluster, clock=clock, timeout=5.0,
                        config={"heartbeat_timeout": 5.0})
        for node, ts in [("n1", 0.0), ("n2", 0.0), ("n3", 8.0), ("n4", 8.0)]:
            node_a.heartbeat(node, ts, 1)
            node_b.heartbeat(node, ts, 1)
        clock.advance(12.0)
        self.assertEqual(node_a.active(), node_b.active())
        self.assertEqual(node_a.active(), {"n3", "n4"})

    def test_no_split_brain_when_only_half_alive(self):
        # 事故时序：本机超时各算各的，两边对“谁还活着”看法不一致，
        # 各按各的多数派前后脚当选。
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3", "n4", "n5")
        node_a = Quorum(cluster, clock=clock, timeout=30.0,
                        config={"heartbeat_timeout": 5.0})
        node_b = Quorum(cluster, clock=clock, timeout=5.0,
                        config={"heartbeat_timeout": 5.0})
        for node, ts in [("n1", 0.0), ("n2", 0.0), ("n3", 8.0), ("n4", 8.0)]:
            node_a.heartbeat(node, ts, 1)
            node_b.heartbeat(node, ts, 1)
        clock.advance(12.0)
        self.assertIsNone(node_a.elect())
        self.assertIsNone(node_b.elect())


class TestTermGuard(unittest.TestCase):
    def test_stale_term_heartbeat_rejected(self):
        clock = FakeClock()
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=clock, timeout=10.0)
        q.heartbeat("n1", 0.0, 0)
        q.heartbeat("n2", 0.0, 0)
        for _ in range(3):
            q.elect()
        self.assertEqual(q.term(), 3)
        self.assertFalse(q.heartbeat("n3", 0.0, 2))

    def test_stale_term_heartbeat_does_not_count_as_alive(self):
        # 老 leader 醒过来补发过期心跳，绝不能把本该退位的节点算活。
        clock = FakeClock()
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=clock, timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        q.heartbeat("n1", 0.0, 0)
        q.heartbeat("n2", 0.0, 0)
        q.elect()
        clock.advance(20.0)
        self.assertEqual(q.active(), set())
        self.assertFalse(q.heartbeat("n1", 20.0, 0))
        self.assertEqual(q.active(), set())

    def test_stale_term_heartbeat_keeps_fresh_timestamp(self):
        clock = FakeClock()
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=clock, timeout=10.0)
        q.heartbeat("n1", 0.0, 5)
        self.assertEqual(q.term(), 5)
        clock.advance(8.0)
        self.assertFalse(q.heartbeat("n1", 8.0, 3))
        clock.advance(8.0)
        # 旧心跳的 ts=8 没覆盖掉新鲜的 ts=0：若覆盖了，此刻 n1 会误判为活。
        self.assertEqual(q.active(), set())

    def test_higher_term_heartbeat_aligns_term(self):
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock(), timeout=10.0)
        self.assertTrue(q.heartbeat("n1", 0.0, 7))
        self.assertEqual(q.term(), 7)
        self.assertEqual(q.active(), {"n1"})

    def test_same_term_heartbeat_accepted(self):
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock(), timeout=10.0)
        q.heartbeat("n1", 0.0, 4)
        self.assertTrue(q.heartbeat("n1", 1.0, 4))

    def test_failed_elect_does_not_bump_term(self):
        # 票不够不算开过新一任，否则失败的选举会凭空抬高任期门槛。
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock(), timeout=10.0)
        self.assertIsNone(q.elect())
        self.assertEqual(q.term(), 0)


class TestRemovedMembers(unittest.TestCase):
    def test_removed_member_drops_out_of_active_immediately(self):
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3")
        q = Quorum(cluster, clock=clock, timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        for node in ("n1", "n2", "n3"):
            q.heartbeat(node, 0.0, 0)
        cluster.remove("n3")
        self.assertEqual(q.active(), {"n1", "n2"})

    def test_stale_timestamp_of_removed_member_inflates_no_quorum(self):
        # 事故时序：旧时间戳一直参与计票，人数虚高导致不够票也当选。
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3", "n4", "n5")
        q = Quorum(cluster, clock=clock, timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        q.heartbeat("n1", 0.0, 0)
        q.heartbeat("n2", 0.0, 0)
        q.heartbeat("n3", 0.0, 0)
        cluster.remove("n3")
        self.assertIsNone(q.elect())

    def test_heartbeat_from_nonmember_never_counts(self):
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3")
        q = Quorum(cluster, clock=clock, timeout=10.0)
        q.heartbeat("ghost", 0.0, 0)
        self.assertEqual(q.active(), set())
        cluster.remove("ghost")  # 摘一个从未在册的节点也不能出岔子
        self.assertEqual(q.active(), set())


class TestIncidentReplay(unittest.TestCase):
    def test_full_incident_timeline_stays_single_leader(self):
        # 把事故时序串起来：扩容 + 超时分歧 + 老 leader 补发 + 运维摘除，
        # 任何时刻都不允许在不足多数派时拿到 leader 任期。
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3")
        node_a = Quorum(cluster, clock=clock, timeout=30.0,
                        config={"heartbeat_timeout": 5.0})
        node_b = Quorum(cluster, clock=clock, timeout=5.0,
                        config={"heartbeat_timeout": 5.0})
        cluster.add("n4")
        cluster.add("n5")
        for node, ts in [("n1", 0.0), ("n2", 0.0), ("n3", 8.0), ("n4", 8.0)]:
            node_a.heartbeat(node, ts, 1)
            node_b.heartbeat(node, ts, 1)
        clock.advance(12.0)
        # 本机超时各算各的旧毛病下，a 会看到 4 个、b 看到 2 个；修复后
        # 两边统一按协商的 5s，只剩 n3、n4，5 人集群要 3 票，谁都选不上。
        self.assertEqual(node_a.active(), {"n3", "n4"})
        self.assertEqual(node_b.active(), {"n3", "n4"})
        self.assertIsNone(node_a.elect())
        self.assertIsNone(node_b.elect())

        # 运维摘掉当前还算活的 n3，它立刻退出两边的计票（集群剩 4 人）。
        cluster.remove("n3")
        self.assertEqual(node_a.active(), {"n4"})
        self.assertEqual(node_b.active(), {"n4"})

        # b 先收到更高任期的新鲜心跳并凑齐在册多数派当选；a 没收到，
        # 视图依旧不足，选不上。
        for node in ("n1", "n2", "n5"):
            node_b.heartbeat(node, 12.0, 3)
        b_term = node_b.elect()
        self.assertEqual(b_term, 4)
        self.assertIsNone(node_a.elect())

        # 老 leader 醒过来补发早就过期的任期 1 心跳：b 已在任期 4，
        # 必须不认，也不许把已超时的 n1 重新算活。
        clock.advance(8.0)
        self.assertFalse(node_b.heartbeat("n1", 20.0, 1))
        self.assertNotIn("n1", node_b.active())
        self.assertFalse(node_b.heartbeat("n3", 20.0, 1))
        self.assertNotIn("n3", node_b.active())


if __name__ == "__main__":
    unittest.main()
