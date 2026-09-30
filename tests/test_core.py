"""TreeCentroid 现有行为的锁定测试（朴素枚举口径）。"""

import unittest

from centroid.core import (
    CentroidError,
    CentroidInputError,
    TreeCentroid,
    UnknownNode,
)


def chain():
    """0 -> 1 -> 2 的链，边权各 1。"""
    return 3, [(0, 1, 1), (1, 2, 1)]


def weighted_chain():
    """0 -> 1 -> 2 -> 3 的链，边权为 3 / 4 / 5。"""
    return 4, [(0, 1, 3), (1, 2, 4), (2, 3, 5)]


def star():
    """中心 0，叶子 1 / 2 / 3，边权各 1。"""
    return 4, [(0, 1, 1), (0, 2, 1), (0, 3, 1)]


class TestLoad(unittest.TestCase):
    def test_load_and_nodes_sorted(self):
        n, edges = chain()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.nodes(), [0, 1, 2])

    def test_nodes_is_deterministic(self):
        n, edges = chain()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.nodes(), t.nodes())

    def test_zero_nodes_rejected(self):
        t = TreeCentroid()
        with self.assertRaises(CentroidInputError):
            t.load(0, [])

    def test_edge_count_mismatch_rejected(self):
        t = TreeCentroid()
        with self.assertRaises(CentroidInputError):
            t.load(3, [(0, 1, 1)])

    def test_endpoint_out_of_range_rejected(self):
        t = TreeCentroid()
        with self.assertRaises(UnknownNode):
            t.load(3, [(0, 1, 1), (1, 4, 1)])

    def test_non_positive_weight_rejected(self):
        t = TreeCentroid()
        with self.assertRaises(CentroidInputError):
            t.load(3, [(0, 1, 0), (1, 2, 1)])

    def test_disconnected_rejected(self):
        t = TreeCentroid()
        with self.assertRaises(CentroidInputError):
            t.load(4, [(0, 1, 1), (1, 2, 1), (0, 2, 1)])

    def test_use_before_load_raises(self):
        t = TreeCentroid()
        with self.assertRaises(CentroidInputError):
            t.centroid()

    def test_unknown_node_query_rejected(self):
        n, edges = chain()
        t = TreeCentroid()
        t.load(n, edges)
        with self.assertRaises(UnknownNode):
            t.path_stats(0, 9)


class TestSingleNode(unittest.TestCase):
    def test_single_node_centroid(self):
        t = TreeCentroid()
        t.load(1, [])
        self.assertEqual(t.centroid(), 0)
        self.assertEqual(t.centroids(), [0])

    def test_single_node_sizes_and_property(self):
        t = TreeCentroid()
        t.load(1, [])
        self.assertEqual(t.subtree_size(0), {0: 1})
        self.assertEqual(t.largest_component(0), 0)
        self.assertEqual(t.centroid_property(0), (0, False))

    def test_single_node_path_and_count(self):
        t = TreeCentroid()
        t.load(1, [])
        self.assertEqual(t.path_stats(0, 0), (0, 0))
        self.assertEqual(t.count_paths_within(0), 0)


class TestChain(unittest.TestCase):
    def test_subtree_size_from_root(self):
        n, edges = chain()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.subtree_size(0), {0: 3, 1: 2, 2: 1})

    def test_component_sizes(self):
        n, edges = chain()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.component_sizes(0), [2])
        self.assertEqual(t.component_sizes(1), [1, 1])
        self.assertEqual(t.component_sizes(2), [2])

    def test_centroid_is_middle(self):
        n, edges = chain()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.centroid(), 1)
        self.assertEqual(t.centroids(), [1])

    def test_distances(self):
        n, edges = chain()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.path_stats(0, 2), (2, 1))
        self.assertEqual(t.path_stats(1, 1), (0, 0))

    def test_count_paths_within(self):
        n, edges = chain()
        t = TreeCentroid()
        t.load(n, edges)
        # 点对 (0,1) (0,2) (1,2)，距离 1 / 2 / 1
        self.assertEqual(t.count_paths_within(1), 2)
        self.assertEqual(t.count_paths_within(2), 3)


class TestWeightedChain(unittest.TestCase):
    def test_weighted_distance_and_peak(self):
        n, edges = weighted_chain()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.path_stats(0, 3), (12, 5))
        self.assertEqual(t.path_stats(1, 3), (9, 5))

    def test_two_centroids_near_middle(self):
        n, edges = weighted_chain()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.centroid(), 1)
        self.assertEqual(t.centroids(), [1, 2])

    def test_centroid_property_over_half(self):
        n, edges = weighted_chain()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.centroid_property(0), (3, True))
        self.assertEqual(t.centroid_property(1), (2, False))

    def test_count_with_exact_limit(self):
        n, edges = weighted_chain()
        t = TreeCentroid()
        t.load(n, edges)
        # 距离：(0,1)=3 (1,2)=4 (2,3)=5 (0,2)=7 (1,3)=9 (0,3)=12
        self.assertEqual(t.count_paths_within(7), 4)
        self.assertEqual(t.count_paths_within(6), 3)
        self.assertEqual(t.count_paths_within(12), 6)


class TestStar(unittest.TestCase):
    def test_center_is_centroid(self):
        n, edges = star()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.centroid(), 0)
        self.assertEqual(t.centroids(), [0])

    def test_subtree_size_from_center(self):
        n, edges = star()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.subtree_size(0), {0: 4, 1: 1, 2: 1, 3: 1})

    def test_leaf_largest_component(self):
        n, edges = star()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.largest_component(1), 3)

    def test_count_paths_within(self):
        n, edges = star()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.count_paths_within(1), 3)
        self.assertEqual(t.count_paths_within(2), 6)


class TestTwoNodes(unittest.TestCase):
    def test_two_node_centroids(self):
        t = TreeCentroid()
        t.load(2, [(0, 1, 5)])
        self.assertEqual(t.centroid(), 0)
        self.assertEqual(t.centroids(), [0, 1])

    def test_two_node_path(self):
        t = TreeCentroid()
        t.load(2, [(0, 1, 5)])
        self.assertEqual(t.path_stats(0, 1), (5, 5))
        self.assertEqual(t.count_paths_within(4), 0)
        self.assertEqual(t.count_paths_within(5), 1)


class TestScale(unittest.TestCase):
    def test_brute_scale(self):
        n, edges = star()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.brute_scale(), 16)

    def test_brute_pair_scale(self):
        n, edges = star()
        t = TreeCentroid()
        t.load(n, edges)
        self.assertEqual(t.brute_pair_scale(), 6)


class TestErrors(unittest.TestCase):
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(CentroidInputError, CentroidError))
        self.assertTrue(issubclass(UnknownNode, CentroidError))

    def test_repeat_runs_identical(self):
        n, edges = weighted_chain()
        t = TreeCentroid()
        t.load(n, edges)
        first = (t.centroid(), t.centroids(), t.path_stats(0, 3))
        second = (t.centroid(), t.centroids(), t.path_stats(0, 3))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
