"""tarjanlca 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from tarjanlca.tree import (
    Tree, Erro, IllegalArgument, UnknownNode, InvalidForest,
)


def build_forest():
    # 连通块一：根 1，孩子 2、4；2 的孩子 3；4 的孩子 5。
    # 连通块二：根 9，孩子 8。
    return Tree({1: None, 2: 1, 3: 2, 4: 1, 5: 4, 9: None, 8: 9})


class TestBasics(unittest.TestCase):
    def test_nodes_sorted(self):
        self.assertEqual(build_forest().nodes(), [1, 2, 3, 4, 5, 8, 9])

    def test_roots_sorted(self):
        self.assertEqual(build_forest().roots(), [1, 9])

    def test_depth(self):
        t = build_forest()
        self.assertEqual(t.depth(1), 0)
        self.assertEqual(t.depth(2), 1)
        self.assertEqual(t.depth(3), 2)
        self.assertEqual(t.depth(8), 1)

    def test_path_to_root(self):
        t = build_forest()
        self.assertEqual(t.path_to_root(3), [3, 2, 1])
        self.assertEqual(t.path_to_root(8), [8, 9])


class TestLca(unittest.TestCase):
    def test_same_node(self):
        t = build_forest()
        self.assertEqual(t.lca(3, 3), 3)
        self.assertEqual(t.lca(1, 1), 1)

    def test_ancestor_and_descendant(self):
        t = build_forest()
        self.assertEqual(t.lca(1, 3), 1)
        self.assertEqual(t.lca(3, 1), 1)
        self.assertEqual(t.lca(2, 3), 2)

    def test_siblings(self):
        self.assertEqual(build_forest().lca(2, 4), 1)

    def test_cross_branch(self):
        t = build_forest()
        self.assertEqual(t.lca(3, 5), 1)
        self.assertEqual(t.lca(3, 4), 1)

    def test_across_components_returns_none(self):
        t = build_forest()
        self.assertEqual(t.lca(3, 8), None)
        self.assertEqual(t.lca(1, 9), None)

    def test_lca_all(self):
        t = build_forest()
        self.assertEqual(t.lca_all([(1, 3), (3, 5), (3, 8)]), [1, 1, None])


class TestEdges(unittest.TestCase):
    def test_single_node(self):
        t = Tree({1: None})
        self.assertEqual(t.roots(), [1])
        self.assertEqual(t.lca(1, 1), 1)
        self.assertEqual(t.path_to_root(1), [1])

    def test_chain(self):
        t = Tree({1: None, 2: 1, 3: 2, 4: 3, 5: 4})
        self.assertEqual(t.lca(5, 2), 2)
        self.assertEqual(t.depth(5), 4)
        self.assertEqual(t.path_to_root(5), [5, 4, 3, 2, 1])

    def test_missing_node(self):
        with self.assertRaises(UnknownNode):
            build_forest().lca(3, 99)

    def test_errors_share_base(self):
        self.assertTrue(issubclass(IllegalArgument, Erro))
        self.assertTrue(issubclass(UnknownNode, Erro))
        self.assertTrue(issubclass(InvalidForest, Erro))

    def test_non_dict_rejected(self):
        with self.assertRaises(IllegalArgument):
            Tree([(1, None)])

    def test_empty_rejected(self):
        with self.assertRaises(IllegalArgument):
            Tree({})

    def test_missing_parent_rejected(self):
        with self.assertRaises(InvalidForest):
            Tree({1: None, 2: 9})

    def test_cycle_rejected(self):
        with self.assertRaises(InvalidForest):
            Tree({1: 2, 2: 1})


if __name__ == "__main__":
    unittest.main()
