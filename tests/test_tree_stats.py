"""treediam 现有朴素行为的锁定测试（基线，一字不改）。"""

import unittest

from treediam import (
    ForestError,
    Tree,
    all_distance_sums,
    all_distances,
    center,
    centroid,
    components,
    diameter,
    diameter_path,
    distance_sum,
    eccentricity_max,
    farthest_distance,
    farthest_from,
    in_same_root,
    is_tree,
    max_distance_sum_point,
    pair_distance_sum,
)


def chain(root, n, weight=1):
    """一条 root 起、n 个节点的链，逐边权重 weight。"""
    t = Tree(root)
    for i in range(root, root + n - 1):
        t.add_edge(i, i + 1, weight)
    return t


def star(root, leaves, weight=1):
    """以 root 为中心的星形树。"""
    t = Tree(root)
    for leaf in leaves:
        t.add_edge(root, leaf, weight)
    return t


class TestTreeConstruction(unittest.TestCase):
    def test_nodes_sorted(self):
        t = Tree(3)
        t.add_edge(3, 1)
        t.add_edge(3, 2)
        self.assertEqual(t.nodes(), [1, 2, 3])

    def test_root_and_weights(self):
        t = Tree(5, weights="vertex")
        self.assertEqual(t.root, 5)
        self.assertEqual(t.weights, "vertex")

    def test_bad_weights_rejected(self):
        with self.assertRaises(ValueError):
            Tree(0, weights="bogus")

    def test_pairs_lexicographic(self):
        t = star(0, [1, 2])
        self.assertEqual(t.pairs(), [(0, 1), (0, 2), (1, 2)])

    def test_edge_weight_both_directions(self):
        t = star(0, [1], weight=7)
        self.assertEqual(t.edge_weight(0, 1), 7)
        self.assertEqual(t.edge_weight(1, 0), 7)


class TestPathBasics(unittest.TestCase):
    def test_path_on_chain(self):
        t = chain(1, 4)
        self.assertEqual(t.path(1, 4), [1, 2, 3, 4])

    def test_path_is_order_independent(self):
        t = chain(1, 4)
        self.assertEqual(t.path(3, 1), [3, 2, 1])

    def test_path_weight_on_chain(self):
        t = chain(1, 4, weight=2)
        self.assertEqual(t.path_weight(1, 4), 6)

    def test_path_weight_vertex_mode_sums_node_ids(self):
        t = chain(1, 3)
        t2 = Tree(1, weights="vertex")
        t2.add_edge(1, 2)
        t2.add_edge(2, 3)
        self.assertEqual(t2.path_weight(1, 3), 6)

    def test_disconnected_path_raises(self):
        t = Tree(1)
        t.add_edge(1, 2)
        t.add_edge(5, 6)
        with self.assertRaises(KeyError):
            t.path_weight(1, 5)


class TestConnectivity(unittest.TestCase):
    def test_chain_is_tree(self):
        self.assertTrue(is_tree(chain(1, 4)))

    def test_single_node_is_tree(self):
        self.assertTrue(is_tree(Tree(9)))

    def test_forest_is_not_tree(self):
        t = Tree(1)
        t.add_edge(1, 2)
        t.add_edge(5, 6)
        self.assertFalse(is_tree(t))

    def test_components_split(self):
        t = Tree(1)
        t.add_edge(1, 2)
        t.add_edge(5, 6)
        self.assertEqual(components(t), [[1, 2], [5, 6]])

    def test_in_same_root(self):
        t = Tree(1)
        t.add_edge(1, 2)
        t.add_edge(5, 6)
        self.assertTrue(in_same_root(t, 1, 2))
        self.assertFalse(in_same_root(t, 1, 5))


class TestDiameter(unittest.TestCase):
    def test_chain_diameter(self):
        t = chain(1, 4)
        self.assertEqual(diameter(t), (3, 1, 4))

    def test_chain_diameter_path(self):
        t = chain(1, 4)
        self.assertEqual(diameter_path(t), [1, 2, 3, 4])

    def test_weighted_diameter(self):
        t = Tree(0)
        t.add_edge(0, 1, 5)
        t.add_edge(0, 2, -2)
        t.add_edge(2, 3, 1)
        self.assertEqual(diameter(t), (5, 0, 1))

    def test_star_diameter_takes_lexicographic_pair(self):
        t = star(0, [1, 2, 3])
        self.assertEqual(diameter(t), (2, 1, 2))

    def test_single_node_diameter_is_zero(self):
        self.assertEqual(diameter(Tree(7)), (0, 7, 7))

    def test_two_node_diameter(self):
        t = Tree(1)
        t.add_edge(1, 2, 4)
        self.assertEqual(diameter(t), (4, 1, 2))

    def test_forest_diameter_raises(self):
        t = Tree(1)
        t.add_edge(1, 2)
        t.add_edge(5, 6)
        with self.assertRaises(ForestError):
            diameter(t)


class TestFarthestAndSums(unittest.TestCase):
    def test_farthest_from_chain_end(self):
        t = chain(1, 4)
        self.assertEqual(farthest_from(t, 1), (4, 3))

    def test_farthest_distance(self):
        t = chain(1, 4)
        self.assertEqual(farthest_distance(t, 1), 3)

    def test_all_distances(self):
        t = chain(1, 4)
        self.assertEqual(all_distances(t, 1), {1: 0, 2: 1, 3: 2, 4: 3})

    def test_distance_sum(self):
        t = chain(1, 4)
        self.assertEqual(distance_sum(t, 1), 6)

    def test_all_distance_sums(self):
        t = chain(1, 4)
        self.assertEqual(all_distance_sums(t), {1: 6, 2: 4, 3: 4, 4: 6})

    def test_max_distance_sum_point_tie_takes_smaller(self):
        t = chain(1, 4)
        self.assertEqual(max_distance_sum_point(t), (1, 6))

    def test_pair_distance_sum(self):
        t = chain(1, 4)
        self.assertEqual(pair_distance_sum(t), 10)

    def test_eccentricity_max(self):
        t = chain(1, 4)
        self.assertEqual(eccentricity_max(t), (1, 3))


class TestCenterAndCentroid(unittest.TestCase):
    def test_center_of_chain(self):
        t = chain(1, 4)
        self.assertEqual(center(t), (2, 2))

    def test_centroid_of_chain_tie_takes_smaller(self):
        t = chain(1, 4)
        self.assertEqual(centroid(t), 2)

    def test_star_centroid_is_root(self):
        t = star(0, [1, 2, 3, 4])
        self.assertEqual(centroid(t), 0)

    def test_single_node_centroid(self):
        self.assertEqual(centroid(Tree(7)), 7)


class TestDeterminism(unittest.TestCase):
    def test_repeated_diameter_is_stable(self):
        t = star(0, [1, 2, 3])
        self.assertEqual(diameter(t), diameter(t))

    def test_traverse_is_repeatable(self):
        t = chain(1, 4)
        first = t.traverse(3)
        second = t.traverse(3)
        self.assertEqual(first, second)
        self.assertEqual(sorted(set(first)), t.nodes())


if __name__ == "__main__":
    unittest.main()
