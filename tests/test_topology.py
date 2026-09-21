"""拓扑模型基线：节点顺序、机架分组、错误路径。"""

import unittest

from rackplace import ClusterTopology, TopologyError


def build_topology():
    topo = ClusterTopology()
    topo.add_node("a1", "rack-a")
    topo.add_node("a2", "rack-a")
    topo.add_node("b1", "rack-b", weight=2.0)
    topo.add_node("c1", "rack-c")
    return topo


class TopologyTest(unittest.TestCase):
    def test_node_order_follows_attach_order(self):
        topo = build_topology()
        self.assertEqual(topo.node_ids(), ("a1", "a2", "b1", "c1"))
        self.assertEqual(topo.nodes_in_rack("rack-a"), ("a1", "a2"))
        self.assertEqual(len(topo), 4)

    def test_racks_sorted_and_lookup(self):
        topo = build_topology()
        self.assertEqual(topo.racks(), ("rack-a", "rack-b", "rack-c"))
        self.assertEqual(topo.rack_of("b1"), "rack-b")
        self.assertEqual(topo.weight("b1"), 2.0)
        self.assertEqual(topo.total_weight(), 5.0)

    def test_duplicate_node_rejected(self):
        topo = build_topology()
        with self.assertRaises(TopologyError):
            topo.add_node("a1", "rack-b")

    def test_bad_weight_rejected(self):
        topo = ClusterTopology()
        for bad in (0, -1.5):
            with self.assertRaises(TopologyError):
                topo.add_node("n1", "rack-a", weight=bad)
        for bad in ("", None):
            with self.assertRaises(TopologyError):
                topo.add_node("n1", bad)

    def test_remove_node_and_last_node_closes_rack(self):
        topo = build_topology()
        topo.remove_node("c1")
        self.assertFalse(topo.has_node("c1"))
        self.assertEqual(topo.racks(), ("rack-a", "rack-b"))
        topo.remove_node("a1")
        topo.remove_node("a2")
        self.assertEqual(topo.racks(), ("rack-b",))
        with self.assertRaises(TopologyError):
            topo.nodes_in_rack("rack-a")

    def test_missing_lookups_raise(self):
        topo = build_topology()
        with self.assertRaises(TopologyError):
            topo.remove_node("ghost")
        with self.assertRaises(TopologyError):
            topo.node("ghost")
        with self.assertRaises(TopologyError):
            topo.rack_of("ghost")
        with self.assertRaises(TopologyError):
            topo.nodes_in_rack("rack-z")


if __name__ == "__main__":
    unittest.main()
