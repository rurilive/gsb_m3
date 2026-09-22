"""IncrementalTopo 的行为基线：小图上这些语义必须一直成立。"""

import unittest

from topoflow.engine import IncrementalTopo
from topoflow.reference import CycleError, order_problems, reference_order


def make_engine(edges=(), nodes=()):
    engine = IncrementalTopo()
    for node in nodes:
        engine.add_node(node)
    engine.add_edges(edges)
    return engine


def assert_valid(test, engine):
    problems = order_problems(engine.snapshot(), engine.order())
    test.assertEqual(problems, [])


class TestBuildAndQuery(unittest.TestCase):
    def test_fresh_build_matches_reference(self):
        engine = make_engine([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])
        self.assertEqual(engine.order(), reference_order(engine.snapshot()))

    def test_isolated_nodes_are_kept(self):
        self.assertEqual(make_engine(nodes=("x", "y")).order(), ["x", "y"])

    def test_nodes_report_arrival_order(self):
        engine = make_engine([("b", "c")])
        engine.add_node("a")
        self.assertEqual(engine.nodes(), ["b", "c", "a"])

    def test_in_degree_follows_the_edges(self):
        engine = make_engine([("a", "c"), ("b", "c"), ("c", "d")])
        self.assertEqual(engine.in_degree("c"), 2)
        self.assertEqual(engine.in_degree("d"), 1)
        self.assertEqual(engine.in_degree("a"), 0)

    def test_rank_points_into_the_order(self):
        engine = make_engine([("a", "b"), ("b", "c")])
        for index, node in enumerate(engine.order()):
            self.assertEqual(engine.rank(node), index)
        self.assertIsNone(engine.rank("nobody"))


class TestUpdates(unittest.TestCase):
    def test_single_add_keeps_order_valid(self):
        engine = make_engine([("a", "b")])
        engine.order()
        engine.add_edge("b", "c")
        assert_valid(self, engine)

    def test_single_remove_keeps_order_valid(self):
        engine = make_engine([("a", "c"), ("b", "c"), ("c", "d")])
        engine.order()
        self.assertTrue(engine.remove_edge("a", "c"))
        self.assertEqual(engine.in_degree("c"), 1)
        assert_valid(self, engine)

    def test_remove_missing_edge_returns_false(self):
        engine = make_engine([("a", "b")])
        self.assertFalse(engine.remove_edge("b", "a"))
        self.assertFalse(engine.remove_edge("a", "zzz"))

    def test_bulk_remove_keeps_order_valid(self):
        engine = make_engine([("a", "c"), ("b", "c"), ("c", "d")])
        engine.order()
        engine.remove_edges([("a", "c"), ("b", "c")])
        self.assertEqual(engine.in_degree("c"), 0)
        assert_valid(self, engine)

    def test_bulk_add_after_first_query(self):
        engine = make_engine([("a", "b")])
        engine.order()
        engine.add_edges([("b", "c"), ("c", "d")])
        assert_valid(self, engine)

    def test_same_operations_give_the_same_order(self):
        script = [
            ("add", "a", "b"),
            ("add", "c", "b"),
            ("add", "c", "d"),
            ("remove", "a", "b"),
            ("add", "b", "e"),
            ("remove", "c", "b"),
        ]
        orders = []
        for _ in range(2):
            engine = IncrementalTopo()
            for op, u, v in script:
                if op == "add":
                    engine.add_edge(u, v)
                else:
                    engine.remove_edge(u, v)
            orders.append(engine.order())
        self.assertEqual(orders[0], orders[1])


class TestCycles(unittest.TestCase):
    def test_cycle_is_reported(self):
        engine = make_engine([("a", "b"), ("b", "c")])
        engine.add_edge("c", "a")
        self.assertFalse(engine.is_acyclic())
        with self.assertRaises(CycleError):
            engine.order()

    def test_self_loop_is_reported(self):
        engine = make_engine([("a", "b")])
        engine.add_edge("b", "b")
        self.assertFalse(engine.is_acyclic())

    def test_cycle_clears_after_removing_that_edge(self):
        engine = make_engine([("a", "b"), ("b", "c")])
        engine.order()
        engine.add_edge("c", "a")
        self.assertFalse(engine.is_acyclic())
        self.assertTrue(engine.remove_edge("c", "a"))
        self.assertTrue(engine.is_acyclic())
        assert_valid(self, engine)


if __name__ == "__main__":
    unittest.main()
