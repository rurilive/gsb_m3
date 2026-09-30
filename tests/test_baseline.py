"""Tree、树形构造与同构判定现有行为的锁定测试（基线，一字不改）。"""

import unittest

from treehash import (
    QueryError,
    Tree,
    TreeError,
    TreehashError,
    canonical_hash,
    group_isomorphic,
    pairwise_comparison_count,
    rooted_canonical_hash,
    rooted_isomorphic,
    unrooted_isomorphic,
)
from treehash.shapes import (
    balanced,
    chain,
    empty,
    mirrored,
    relabel,
    single,
    star,
)


class TestShapes(unittest.TestCase):
    def test_chain_shape(self):
        t = chain(4)
        self.assertEqual(t.n, 4)
        self.assertEqual(t.degree(0), 1)
        self.assertEqual(t.degree(1), 2)
        self.assertEqual(t.edges(), [(0, 1), (1, 2), (2, 3)])

    def test_star_shape(self):
        t = star(3)
        self.assertEqual(t.n, 4)
        self.assertEqual(t.degree(0), 3)
        self.assertEqual(sorted(t.neighbors(0)), [1, 2, 3])

    def test_balanced_shape_is_deterministic(self):
        t = balanced(7)
        self.assertEqual(sorted(t.neighbors(0)), [1, 2])
        self.assertEqual(t.degree(3), 1)

    def test_single_and_empty(self):
        self.assertEqual(single().n, 1)
        self.assertEqual(empty().n, 0)

    def test_relabel_keeps_edges_and_shape(self):
        t = relabel(chain(4), [2, 0, 3, 1])
        self.assertEqual(t.n, 4)
        self.assertEqual(t.edges(), [(0, 2), (0, 3), (1, 3)])

    def test_mirrored_star(self):
        self.assertEqual(mirrored(3).degree(3), 3)


class TestTreeConstruction(unittest.TestCase):
    def test_n_must_be_non_negative(self):
        with self.assertRaises(TreeError):
            Tree(-1)

    def test_n_must_be_int(self):
        with self.assertRaises(TreeError):
            Tree(2.5)

    def test_bool_is_not_int(self):
        with self.assertRaises(TreeError):
            Tree(True)

    def test_edge_out_of_range(self):
        t = Tree(3)
        with self.assertRaises(TreeError):
            t.add_edge(0, 3)

    def test_self_loop_rejected(self):
        t = Tree(3)
        with self.assertRaises(TreeError):
            t.add_edge(1, 1)

    def test_duplicate_edge_rejected(self):
        t = Tree(3)
        t.add_edge(0, 1)
        with self.assertRaises(TreeError):
            t.add_edge(1, 0)

    def test_error_hierarchy(self):
        self.assertTrue(issubclass(TreeError, TreehashError))
        self.assertTrue(issubclass(QueryError, TreehashError))

    def test_error_hierarchy_from_package(self):
        self.assertTrue(issubclass(TreehashError, Exception))


class TestCentroids(unittest.TestCase):
    def test_chain_has_two_centroids(self):
        self.assertEqual(chain(4).centroids(), [1, 2])

    def test_star_centroid_is_center(self):
        self.assertEqual(star(3).centroids(), [0])

    def test_balanced_centroid_is_root(self):
        self.assertEqual(balanced(7).centroids(), [0])

    def test_empty_tree_has_no_centroid(self):
        self.assertEqual(empty().centroids(), [])

    def test_single_tree_centroid(self):
        self.assertEqual(single().centroids(), [0])


class TestRootedIsomorphic(unittest.TestCase):
    def test_chain_ends_are_isomorphic(self):
        t = chain(4)
        self.assertTrue(rooted_isomorphic(t, 0, t, 3))

    def test_chain_end_not_isomorphic_to_middle(self):
        t = chain(4)
        self.assertFalse(rooted_isomorphic(t, 0, t, 1))

    def test_relabeled_roots_isomorphic(self):
        a = chain(5)
        b = relabel(a, [4, 3, 2, 1, 0])
        self.assertTrue(rooted_isomorphic(a, 2, b, 2))
        self.assertTrue(rooted_isomorphic(a, 0, b, 4))

    def test_single_rooted_isomorphic(self):
        self.assertTrue(rooted_isomorphic(single(), 0, single(), 0))

    def test_different_size_never_isomorphic(self):
        self.assertFalse(rooted_isomorphic(chain(3), 0, chain(4), 0))

    def test_bad_root_rejected(self):
        with self.assertRaises(QueryError):
            rooted_isomorphic(chain(3), 5, chain(3), 0)


class TestUnrootedIsomorphic(unittest.TestCase):
    def test_star_and_mirror(self):
        self.assertTrue(unrooted_isomorphic(star(3), mirrored(3)))

    def test_chain_and_relabel(self):
        self.assertTrue(unrooted_isomorphic(chain(5), relabel(chain(5), [4, 3, 2, 1, 0])))

    def test_star_not_chain(self):
        self.assertFalse(unrooted_isomorphic(star(3), chain(4)))

    def test_empty_trees_are_isomorphic(self):
        self.assertTrue(unrooted_isomorphic(empty(), empty()))

    def test_empty_not_isomorphic_to_single(self):
        self.assertFalse(unrooted_isomorphic(empty(), single()))


class TestCanonicalHash(unittest.TestCase):
    def test_rooted_hash_deterministic(self):
        t = chain(5)
        self.assertEqual(rooted_canonical_hash(t, 0), rooted_canonical_hash(t, 0))

    def test_rooted_hash_matches_isomorphism(self):
        t = chain(4)
        self.assertEqual(rooted_canonical_hash(t, 0), rooted_canonical_hash(t, 3))

    def test_rooted_hash_differs_for_non_isomorphic(self):
        t = star(3)
        self.assertNotEqual(rooted_canonical_hash(t, 0), rooted_canonical_hash(t, 1))

    def test_canonical_hash_invariant_under_relabel(self):
        a = chain(6)
        b = relabel(a, [5, 4, 3, 2, 1, 0])
        self.assertEqual(canonical_hash(a), canonical_hash(b))

    def test_canonical_hash_empty_is_zero(self):
        self.assertEqual(canonical_hash(empty()), 0)

    def test_bad_tree_rejected(self):
        with self.assertRaises(QueryError):
            canonical_hash("not a tree")


class TestGrouping(unittest.TestCase):
    def test_group_by_isomorphism(self):
        trees = [chain(4), star(3), relabel(chain(4), [3, 2, 1, 0]), mirrored(3)]
        self.assertEqual(group_isomorphic(trees), [[0, 2], [1, 3]])

    def test_group_order_by_min_index(self):
        self.assertEqual(group_isomorphic([star(3), chain(4)]), [[0], [1]])

    def test_group_empty_list(self):
        self.assertEqual(group_isomorphic([]), [])

    def test_bad_member_rejected(self):
        with self.assertRaises(QueryError):
            group_isomorphic([chain(2), 1])


class TestPairwiseCount(unittest.TestCase):
    def test_count_matches_grouping_rounds(self):
        trees = [chain(4), star(3), relabel(chain(4), [3, 2, 1, 0]), mirrored(3)]
        self.assertEqual(pairwise_comparison_count(trees), 4)

    def test_count_all_distinct(self):
        trees = [chain(2), star(2), chain(1)]
        self.assertEqual(pairwise_comparison_count(trees), 3)

    def test_count_empty(self):
        self.assertEqual(pairwise_comparison_count([]), 0)


if __name__ == "__main__":
    unittest.main()
