"""体检模块的基线：干净布局过检，脏布局每种毛病都要报出来。"""

import unittest

from rackplace import ClusterTopology, Placement, check, summary


def build_topology():
    topo = ClusterTopology()
    for index in range(4):
        topo.add_node("n%d" % index, "rack-%d" % index)
    return topo


class CheckTest(unittest.TestCase):
    def test_clean_layout_passes(self):
        plan = Placement({
            0: ["n0", "n1"],
            1: ["n2", "n3"],
            2: ["n0", "n1"],
            3: ["n2", "n3"],
        })
        self.assertEqual(check(plan, build_topology(), replicas=2), [])

    def test_duplicate_node_in_partition(self):
        plan = Placement({0: ["n0", "n0"]})
        problems = check(plan, build_topology(), replicas=2)
        self.assertTrue(any("0" in line for line in problems))
        self.assertEqual(len(problems), 1)

    def test_missing_node_is_reported(self):
        plan = Placement({0: ["n0", "ghost"]})
        problems = check(plan, build_topology(), replicas=2)
        self.assertEqual(len(problems), 1)
        self.assertIn("ghost", problems[0])

    def test_wrong_replica_count(self):
        plan = Placement({0: ["n0", "n1", "n2"]})
        problems = check(plan, build_topology(), replicas=2)
        self.assertEqual(len(problems), 1)
        self.assertIn("3", problems[0])

    def test_replica_count_optional(self):
        plan = Placement({0: ["n0", "n1", "n2"]})
        self.assertEqual(check(plan, build_topology()), [])


class SummaryTest(unittest.TestCase):
    def test_loads_cover_all_nodes(self):
        plan = Placement({0: ["n0", "n1"], 1: ["n0", "n2"]})
        stats = summary(plan, build_topology())
        self.assertEqual(stats["loads"], {"n0": 2, "n1": 1, "n2": 1, "n3": 0})
        self.assertEqual(stats["heaviest"], "n0")
        self.assertEqual(stats["max_load"], 2)
        self.assertEqual(stats["min_load"], 0)

    def test_empty_layout(self):
        stats = summary(Placement({}), build_topology())
        self.assertIsNone(stats["heaviest"])
        self.assertEqual(stats["max_load"], 0)


if __name__ == "__main__":
    unittest.main()
