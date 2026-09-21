"""放置快照与平铺轮询的基线：形状钉死，外部靠它认布局。"""

import unittest

from rackplace import ClusterTopology, Placement, PlacementError, migration_count
from rackplace import round_robin


def build_topology():
    topo = ClusterTopology()
    for rack in ("rack-a", "rack-b", "rack-c"):
        for slot in (1, 2):
            topo.add_node("%s%d" % (rack[-1], slot), rack)
    return topo


class RoundRobinTest(unittest.TestCase):
    def test_flat_round_robin_order_is_pinned(self):
        topo = build_topology()
        plan = round_robin(topo, range(4), replicas=3)
        self.assertEqual(plan.owners(0), ("a1", "a2", "b1"))
        self.assertEqual(plan.owners(1), ("b2", "c1", "c2"))
        self.assertEqual(plan.owners(2), ("a1", "a2", "b1"))
        self.assertEqual(plan.owners(3), ("b2", "c1", "c2"))

    def test_single_replica_walks_the_list(self):
        topo = build_topology()
        plan = round_robin(topo, range(7), replicas=1)
        self.assertEqual(plan.owners(0), ("a1",))
        self.assertEqual(plan.owners(5), ("c2",))
        self.assertEqual(plan.owners(6), ("a1",))

    def test_errors(self):
        empty = ClusterTopology()
        with self.assertRaises(PlacementError):
            round_robin(empty, range(3), replicas=1)
        topo = build_topology()
        with self.assertRaises(PlacementError):
            round_robin(topo, range(3), replicas=0)
        with self.assertRaises(PlacementError):
            round_robin(topo, range(3), replicas=7)
        with self.assertRaises(PlacementError):
            round_robin(topo, [1, 2, 2], replicas=2)


class PlacementTest(unittest.TestCase):
    def test_snapshot_does_not_alias_input(self):
        source = {0: ["a1", "a2"], 1: ["b1", "b2"]}
        plan = Placement(source)
        source[0].append("b1")
        self.assertEqual(plan.owners(0), ("a1", "a2"))
        dumped = plan.as_dict()
        dumped[1].append("c1")
        self.assertEqual(plan.owners(1), ("b1", "b2"))

    def test_partitions_and_loads(self):
        plan = Placement({2: ["b1"], 0: ["a1", "a2"], 1: ["a2"]})
        self.assertEqual(plan.partitions(), (0, 1, 2))
        self.assertEqual(plan.size(), 3)
        self.assertEqual(plan.replica_total(), 4)
        self.assertEqual(plan.node_loads(), {"a1": 1, "a2": 2, "b1": 1})

    def test_unknown_partition_raises(self):
        plan = Placement({0: ["a1"]})
        with self.assertRaises(PlacementError):
            plan.owners(9)
        self.assertIsNone(plan.get(9))
        with self.assertRaises(PlacementError):
            Placement({0: []})


class MigrationCountTest(unittest.TestCase):
    def test_identical_layout_moves_nothing(self):
        plan = Placement({0: ["a1", "a2"], 1: ["b1", "c1"]})
        self.assertEqual(migration_count(plan, plan), 0)

    def test_reordering_is_not_a_migration(self):
        before = Placement({0: ["a1", "a2"], 1: ["b1", "c1"]})
        after = Placement({0: ["a2", "a1"], 1: ["c1", "b1"]})
        self.assertEqual(migration_count(before, after), 0)

    def test_changed_and_new_partitions_count(self):
        before = Placement({0: ["a1", "a2"], 1: ["b1", "c1"]})
        after = Placement({0: ["a1", "b2"], 1: ["b1", "c1"], 2: ["c1", "a1"]})
        self.assertEqual(migration_count(before, after), 2)


if __name__ == "__main__":
    unittest.main()
