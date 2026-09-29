"""Scheduler 现有行为的锁定测试。"""

import unittest

from dagsched.scheduler import (
    CycleError,
    DependencyNotFound,
    Scheduler,
    UnknownTask,
)


def build(pairs):
    """按 (task, dep) 列表建图，返回 Scheduler。"""
    s = Scheduler()
    for name in sorted({n for pair in pairs for n in pair}):
        s.add_task(name)
    for task, dep in pairs:
        s.add_dependency(task, dep)
    return s


class TestRegistration(unittest.TestCase):
    def test_add_task_and_has_task(self):
        s = Scheduler()
        s.add_task("a")
        self.assertTrue(s.has_task("a"))
        self.assertFalse(s.has_task("b"))

    def test_add_task_is_idempotent(self):
        s = Scheduler()
        s.add_task("a")
        s.add_task("a")
        self.assertEqual(s.tasks(), ["a"])

    def test_invalid_name_raises(self):
        s = Scheduler()
        with self.assertRaises(ValueError):
            s.add_task("")
        with self.assertRaises(ValueError):
            s.add_task(None)

    def test_dependency_on_unknown_task_raises(self):
        s = Scheduler()
        s.add_task("a")
        with self.assertRaises(DependencyNotFound):
            s.add_dependency("a", "ghost")

    def test_dependency_from_unknown_task_raises(self):
        s = Scheduler()
        s.add_task("a")
        with self.assertRaises(UnknownTask):
            s.add_dependency("ghost", "a")

    def test_self_dependency_raises(self):
        s = Scheduler()
        s.add_task("a")
        with self.assertRaises(CycleError):
            s.add_dependency("a", "a")


class TestTopoOrder(unittest.TestCase):
    def test_chain(self):
        s = build([("b", "a"), ("c", "b")])
        self.assertEqual(s.topo_order(), ["a", "b", "c"])

    def test_diamond(self):
        s = build([("b", "a"), ("c", "a"), ("d", "b"), ("d", "c")])
        order = s.topo_order()
        self.assertEqual(order.index("a"), 0)
        self.assertLess(order.index("b"), order.index("d"))
        self.assertLess(order.index("c"), order.index("d"))

    def test_topo_order_is_deterministic(self):
        s = build([("b", "a"), ("c", "a"), ("d", "b")])
        self.assertEqual(s.topo_order(), s.topo_order())

    def test_duplicate_dependency_raises(self):
        s = build([("b", "a")])
        with self.assertRaises(CycleError):
            s.add_dependency("b", "a")

    def test_cycle_returns_remaining_nodes(self):
        s = Scheduler()
        for n in "abc":
            s.add_task(n)
        s.add_dependency("b", "a")
        s.add_dependency("a", "b")
        self.assertEqual(s.topo_order(), ["a", "b"])


class TestNeighbors(unittest.TestCase):
    def test_predecessors_and_successors(self):
        s = build([("b", "a"), ("c", "a"), ("d", "b")])
        self.assertEqual(s.predecessors("b"), {"a"})
        self.assertEqual(s.successors("a"), {"b", "c"})
        self.assertEqual(s.predecessors("a"), set())

    def test_predecessors_of_unknown_raises(self):
        s = Scheduler()
        with self.assertRaises(UnknownTask):
            s.predecessors("ghost")


class TestReadyTasks(unittest.TestCase):
    def test_roots_are_ready(self):
        s = build([("b", "a")])
        self.assertEqual(s.ready_tasks(), ["a"])

    def test_ready_after_done(self):
        s = build([("b", "a"), ("c", "b")])
        self.assertEqual(s.ready_tasks({"a"}), ["b"])
        self.assertEqual(s.ready_tasks({"a", "b"}), ["c"])

    def test_done_tasks_are_excluded(self):
        s = build([])
        s.add_task("a")
        self.assertEqual(s.ready_tasks(), ["a"])
        self.assertEqual(s.ready_tasks({"a"}), [])


class TestDetectCycle(unittest.TestCase):
    def test_no_cycle_returns_none(self):
        s = build([("b", "a"), ("c", "b")])
        self.assertIsNone(s.detect_cycle())

    def test_detects_cycle(self):
        s = Scheduler()
        for n in "abc":
            s.add_task(n)
        s.add_task("d")
        s.add_dependency("b", "a")
        s.add_dependency("c", "b")
        s.add_dependency("a", "c")
        cyc = s.detect_cycle()
        self.assertIsNotNone(cyc)
        self.assertEqual(set(cyc), {"a", "b", "c"})

    def test_cycle_excludes_innocent_node(self):
        s = Scheduler()
        for n in "abc":
            s.add_task(n)
        s.add_dependency("b", "a")
        s.add_dependency("a", "b")
        cyc = s.detect_cycle()
        self.assertEqual(set(cyc), {"a", "b"})
        self.assertNotIn("c", cyc)


if __name__ == "__main__":
    unittest.main()