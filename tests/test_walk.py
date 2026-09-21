"""objlife.walk 基线：从一组根出发的可达集合与分层遍历。"""

import unittest

from objlife import ObjectStore, layers, reachable


class WalkCase(unittest.TestCase):
    """page 挂 header 和 body，两个块共用一份 style，外部引用都放光。"""

    def setUp(self):
        self.store = ObjectStore()
        self.page = self.store.create("page")
        self.header = self.store.create("header")
        self.body = self.store.create("body")
        self.style = self.store.create("style")
        self.store.link(self.page, self.header)
        self.store.link(self.page, self.body)
        self.store.link(self.header, self.style)
        self.store.link(self.body, self.style)
        for oid in (self.header, self.body, self.style):
            self.store.release(oid)


class TestReachable(WalkCase):

    def test_reaches_transitively(self):
        got = reachable(self.store, [self.page])
        self.assertEqual(got, {self.page, self.header, self.body, self.style})

    def test_roots_are_included(self):
        self.assertEqual(reachable(self.store, [self.style]), {self.style})

    def test_cycle_terminates(self):
        a = self.store.create("a")
        b = self.store.create("b")
        self.store.link(a, b)
        self.store.link(b, a)
        self.assertEqual(reachable(self.store, [a]), {a, b})

    def test_unreachable_objects_excluded(self):
        orphan = self.store.create("orphan")
        got = reachable(self.store, [self.page])
        self.assertNotIn(orphan, got)

    def test_dead_roots_ignored(self):
        dead = self.store.create("dead")
        self.store.release(dead)
        self.assertEqual(reachable(self.store, [dead]), set())
        self.assertEqual(reachable(self.store, []), set())


class TestLayers(WalkCase):

    def test_layers_by_distance(self):
        got = layers(self.store, [self.page])
        self.assertEqual(got, [[self.page], [self.header, self.body], [self.style]])

    def test_cycle_does_not_repeat_nodes(self):
        a = self.store.create("a")
        b = self.store.create("b")
        self.store.link(a, b)
        self.store.link(b, a)
        self.assertEqual(layers(self.store, [a]), [[a], [b]])

    def test_duplicate_roots_collapsed(self):
        got = layers(self.store, [self.page, self.page])
        self.assertEqual(got[0], [self.page])


if __name__ == "__main__":
    unittest.main()
