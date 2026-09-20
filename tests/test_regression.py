"""双主事故的防回归测试。

对应四类根因：
1. 多数派门槛必须按当前在册成员动态计算（扩容/摘除都要重算）；
2. 活跃判定必须用集群协商超时，不能各节点按本机配置各算各的；
3. 任期只能往前走，旧任期心跳一律不采纳、不刷新活跃时间；
4. 摘除的成员立刻退出活跃集合与计票。

另锁两个配套不变量：选不上不涨任期；从未在册的节点报活也不计数。
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
    def test_majority_tracks_expansion(self):
        cluster = cluster_of("n1", "n2", "n3")
        q = Quorum(cluster, clock=FakeClock(), timeout=10.0)
        self.assertEqual(q.majority(), 2)
        cluster.add("n4")
        cluster.add("n5")
        self.assertEqual(q.majority(), 3)

    def test_majority_tracks_shrink(self):
        cluster = cluster_of("n1", "n2", "n3", "n4", "n5")
        q = Quorum(cluster, clock=FakeClock(), timeout=10.0)
        self.assertEqual(q.majority(), 3)
        cluster.remove("n5")
        self.assertEqual(q.majority(), 3)  # 4 人集群仍需 3 票
        cluster.remove("n4")
        self.assertEqual(q.majority(), 2)

    def test_two_votes_after_expansion_are_not_enough(self):
        # 事故现场：备用节点扩容进来后，老进程还按 3 人门槛凑票。
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3")
        q = Quorum(cluster, clock=clock, timeout=10.0)
        cluster.add("n4")
        cluster.add("n5")
        q.heartbeat("n1", 0.0, 1)
        q.heartbeat("n2", 0.0, 1)
        self.assertEqual(q.active(), {"n1", "n2"})
        self.assertIsNone(q.elect())

    def test_quorum_regained_after_expansion_can_elect(self):
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3")
        q = Quorum(cluster, clock=clock, timeout=10.0)
        cluster.add("n4")
        cluster.add("n5")
        for node in ("n1", "n2", "n3"):
            q.heartbeat(node, 0.0, 1)
        # 心跳里的任期 1 已被跟进，当选后任期在此基础上加一。
        self.assertEqual(q.term(), 1)
        self.assertEqual(q.elect(), 2)


class TestNegotiatedTimeoutActive(unittest.TestCase):
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
        # 同一时钟、同一协商超时：本机 timeout 配置不同也必须得出同一份活集。
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
        self.assertEqual(node_a.active(), {"n3", "n4"})
        self.assertEqual(node_a.active(), node_b.active())

    def test_neither_divergent_view_can_elect(self):
        # 复放双主时序：两边都凑不齐协商视图下的多数派，谁都不许当选。
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
        self.assertIsNone(node_a.elect())
        self.assertIsNone(node_b.elect())

    def test_falls_back_to_local_timeout_without_config(self):
        clock = FakeClock()
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=clock, timeout=3.0)
        q.heartbeat("n1", 0.0, 1)
        clock.advance(2.0)
        self.assertEqual(q.active(), {"n1"})
        clock.advance(2.0)
        self.assertEqual(q.active(), set())


class TestTermMonotonicity(unittest.TestCase):
    def test_stale_term_heartbeat_rejected(self):
        clock = FakeClock()
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=clock, timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        for node in ("n1", "n2", "n3"):
            q.heartbeat(node, 0.0, 0)
        q.elect()  # 任期进到 1
        self.assertFalse(q.heartbeat("n3", 0.0, 0))

    def test_stale_term_heartbeat_does_not_refresh_liveness(self):
        # 旧 leader 醒来补发过期任期心跳，不能把本该退位的节点算活。
        clock = FakeClock()
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=clock, timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        q.heartbeat("n1", 0.0, 0)
        q.heartbeat("n2", 0.0, 0)
        for _ in range(5):
            q.elect()
        self.assertEqual(q.term(), 5)
        clock.advance(20.0)
        self.assertFalse(q.heartbeat("n3", clock.now, 2))
        self.assertEqual(q.active(), set())

    def test_equal_term_heartbeat_accepted(self):
        clock = FakeClock()
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=clock, timeout=10.0)
        for node in ("n1", "n2", "n3"):
            q.heartbeat(node, 0.0, 0)
        q.elect()  # 任期 1
        self.assertTrue(q.heartbeat("n2", clock.now, 1))

    def test_newer_term_heartbeat_advances_term(self):
        clock = FakeClock()
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=clock, timeout=10.0)
        self.assertTrue(q.heartbeat("n1", 0.0, 4))
        self.assertEqual(q.term(), 4)
        # 跟进新任期后，更旧的任期心跳同样被拒。
        self.assertFalse(q.heartbeat("n2", 0.0, 3))

    def test_failed_election_does_not_increment_term(self):
        clock = FakeClock()
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=clock, timeout=10.0)
        q.heartbeat("n1", 0.0, 0)
        self.assertIsNone(q.elect())
        self.assertEqual(q.term(), 0)
        # 失败的竞选没白涨任期，同任期心跳之后仍可被采纳。
        self.assertTrue(q.heartbeat("n2", clock.now, 0))


class TestRemovedMembers(unittest.TestCase):
    def test_removed_member_drops_from_active_immediately(self):
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3", "n4", "n5")
        q = Quorum(cluster, clock=clock, timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        for node in ("n1", "n2", "n3"):
            q.heartbeat(node, 0.0, 0)
        cluster.remove("n3")
        self.assertEqual(q.active(), {"n1", "n2"})

    def test_removed_member_old_timestamp_not_counted(self):
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3", "n4", "n5")
        q = Quorum(cluster, clock=clock, timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        for node in ("n1", "n2", "n3"):
            q.heartbeat(node, 0.0, 0)
        cluster.remove("n3")
        # 4 个在册成员需 3 票，实际只剩 2 活：不许当选。
        self.assertIsNone(q.elect())
        self.assertEqual(q.term(), 0)

    def test_readded_member_counts_only_after_new_heartbeat(self):
        # 摘除期间旧时间戳不会一直有效；重新加回来也要重新报活。
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3")
        q = Quorum(cluster, clock=clock, timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        for node in ("n1", "n2", "n3"):
            q.heartbeat(node, 0.0, 0)
        cluster.remove("n3")
        clock.advance(20.0)
        cluster.add("n3")
        self.assertEqual(q.active(), set())
        q.heartbeat("n1", clock.now, 0)
        q.heartbeat("n2", clock.now, 0)
        q.heartbeat("n3", clock.now, 0)
        self.assertEqual(q.active(), {"n1", "n2", "n3"})


class TestUnknownMembersNeverCount(unittest.TestCase):
    def test_heartbeat_from_never_member_not_counted(self):
        clock = FakeClock()
        cluster = cluster_of("n1", "n2", "n3")
        q = Quorum(cluster, clock=clock, timeout=10.0)
        q.heartbeat("n1", 0.0, 1)
        q.heartbeat("stranger", 0.0, 1)
        self.assertEqual(q.active(), {"n1"})
        self.assertIsNone(q.elect())


if __name__ == "__main__":
    unittest.main()
