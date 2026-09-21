"""Cluster 与 Node 的行为基线。"""

import unittest

from membersim.cluster import Cluster
from membersim.member import ALIVE, DEAD


class TestStep(unittest.TestCase):
    def setUp(self):
        self.cluster = Cluster(["n1", "n2", "n3"])

    def test_step_advances_clock_and_counts_periods(self):
        self.cluster.step()
        self.cluster.step()
        self.assertEqual(self.cluster.clock.now, 2.0)
        self.assertEqual(self.cluster.steps, 2)
        self.assertEqual(self.cluster.node("n1").periods, 2)

    def test_run_advances_multiple_periods(self):
        self.cluster.run(3)
        self.assertEqual(self.cluster.clock.now, 3.0)

    def test_all_nodes_alive_by_default(self):
        self.assertEqual(self.cluster.alive_nodes(), ("n1", "n2", "n3"))
        self.assertEqual(self.cluster.node("n2").alive_members(), ("n1", "n2", "n3"))

    def test_each_node_has_its_own_table(self):
        self.cluster.node("n1").mark_down("n3")
        views = self.cluster.views()
        self.assertEqual(views["n1"]["n3"], DEAD)
        self.assertEqual(views["n2"]["n3"], ALIVE)
        self.assertFalse(self.cluster.views_agree())

    def test_views_only_from_alive_nodes(self):
        self.cluster.schedule.crash("n3", 0.0)
        self.assertEqual(sorted(self.cluster.views()), ["n1", "n2"])


class TestCrashedNodes(unittest.TestCase):
    def setUp(self):
        self.cluster = Cluster(["n1", "n2"])
        self.cluster.schedule.crash("n2", 0.0)

    def test_crashed_node_is_skipped(self):
        self.cluster.run(2)
        self.assertEqual(self.cluster.node("n2").periods, 0)
        self.assertEqual(self.cluster.node("n1").periods, 2)
        self.assertEqual(self.cluster.alive_nodes(), ("n1",))

    def test_message_to_crashed_node_is_dropped(self):
        self.cluster.node("n1").send_to("n2", ("table", {}))
        self.cluster.step()
        self.assertEqual(self.cluster.dropped_to_down, 1)

    def test_restart_puts_node_back(self):
        self.cluster.run(2)
        self.cluster.schedule.restart("n2", 2.0)
        self.assertEqual(self.cluster.alive_nodes(), ("n1", "n2"))
        self.cluster.step()
        self.assertEqual(self.cluster.node("n2").periods, 1)


class TestNaiveSync(unittest.TestCase):
    """现成的整表同步：显式调用才动，能把状态搬给一个邻居。"""

    def setUp(self):
        self.cluster = Cluster(["n1", "n2", "n3"])

    def test_announce_copies_view_to_peer(self):
        self.cluster.node("n1").mark_down("n3")
        self.cluster.node("n1").announce("n2")
        self.cluster.step()
        self.assertEqual(self.cluster.node("n2").status_of("n3"), DEAD)
        self.assertEqual(self.cluster.node("n3").status_of("n3"), ALIVE)

    def test_announce_stops_at_partition(self):
        self.cluster.network.partition(["n1"], ["n2", "n3"])
        self.assertFalse(self.cluster.node("n1").send_to("n2", ("table", {})))


if __name__ == "__main__":
    unittest.main()
