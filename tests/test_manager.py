"""管理器的基线：布局生命周期、增删节点的接口形状、确定性。"""

import unittest

from rackplace import (
    ClusterTopology,
    PlacementError,
    PlacementManager,
    TopologyError,
)


def build_topology():
    topo = ClusterTopology()
    for rack in ("az1-r1", "az1-r2", "az1-r3"):
        for slot in (1, 2):
            topo.add_node("%s-n%d" % (rack, slot), rack)
    return topo


def assert_well_formed(test, plan, topo, replicas):
    """布局的形状下限：分区齐、副本数对、节点都在、同分区不重号。"""
    test.assertEqual(plan.size(), 6)
    for partition in plan.partitions():
        owners = plan.owners(partition)
        test.assertEqual(len(owners), replicas)
        test.assertEqual(len(set(owners)), replicas)
        for node_id in owners:
            test.assertTrue(topo.has_node(node_id))


class ManagerTest(unittest.TestCase):
    def setUp(self):
        self.topo = build_topology()
        self.manager = PlacementManager(
            self.topo, range(6), replicas=3, seed=2026)

    def test_no_layout_until_first_rebalance(self):
        self.assertIsNone(self.manager.current())
        plan = self.manager.rebalance()
        self.assertEqual(self.manager.current(), plan)
        assert_well_formed(self, plan, self.topo, 3)

    def test_add_node_keeps_layout_shape(self):
        self.manager.rebalance()
        plan = self.manager.add_node("az2-r1-n1", "az2-r1", weight=2.0)
        self.assertTrue(self.topo.has_node("az2-r1-n1"))
        assert_well_formed(self, plan, self.topo, 3)
        self.assertEqual(self.manager.current(), plan)

    def test_remove_node_clears_its_references(self):
        self.manager.rebalance()
        plan = self.manager.remove_node("az1-r2-n1")
        self.assertFalse(self.topo.has_node("az1-r2-n1"))
        for owners in plan.as_dict().values():
            self.assertNotIn("az1-r2-n1", owners)
        assert_well_formed(self, plan, self.topo, 3)

    def test_same_input_same_seed_same_layout(self):
        twin_topo = build_topology()
        twin = PlacementManager(twin_topo, range(6), replicas=3, seed=2026)
        self.assertEqual(self.manager.rebalance(), twin.rebalance())
        self.assertEqual(
            self.manager.add_node("az2-r1-n1", "az2-r1", weight=2.0),
            twin.add_node("az2-r1-n1", "az2-r1", weight=2.0),
        )

    def test_errors(self):
        with self.assertRaises(PlacementError):
            PlacementManager(build_topology(), [0, 1, 1], replicas=3)
        with self.assertRaises(PlacementError):
            PlacementManager(build_topology(), range(3), replicas=0)
        with self.assertRaises(TopologyError):
            self.manager.remove_node("ghost")
        tiny = ClusterTopology()
        tiny.add_node("only", "rack-a")
        with self.assertRaises(PlacementError):
            PlacementManager(tiny, range(2), replicas=3).rebalance()


if __name__ == "__main__":
    unittest.main()
