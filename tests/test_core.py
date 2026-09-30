"""StringPool 现有行为的锁定测试。"""

import unittest

from polyhash.core import PolyHashError, StringPool, build_text


def sample():
    pool = StringPool()
    pool.add("abcdef")
    pool.add("abcxyz")
    pool.add("abcdef")
    pool.add("hello")
    return pool


class TestBuildText(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(build_text(7, 40), build_text(7, 40))

    def test_seed_changes_text(self):
        self.assertNotEqual(build_text(1, 30), build_text(2, 30))

    def test_length(self):
        self.assertEqual(len(build_text(3, 25)), 25)

    def test_lowercase_only(self):
        self.assertTrue(build_text(9, 60).islower())

    def test_negative_length_raises(self):
        with self.assertRaises(PolyHashError):
            build_text(1, -1)


class TestRegistry(unittest.TestCase):
    def test_add_returns_index(self):
        pool = StringPool()
        self.assertEqual(pool.add("a"), 0)
        self.assertEqual(pool.add("b"), 1)

    def test_size(self):
        self.assertEqual(sample().size(), 4)

    def test_get(self):
        self.assertEqual(sample().get(2), "abcdef")

    def test_get_out_of_range(self):
        with self.assertRaises(PolyHashError):
            sample().get(99)

    def test_get_negative(self):
        with self.assertRaises(PolyHashError):
            sample().get(-1)

    def test_add_non_string_raises(self):
        with self.assertRaises(PolyHashError):
            StringPool().add(123)


class TestEqual(unittest.TestCase):
    def test_equal_same(self):
        self.assertTrue(sample().equal(0, 2))

    def test_equal_different(self):
        self.assertFalse(sample().equal(0, 1))

    def test_equal_same_index(self):
        self.assertTrue(sample().equal(3, 3))

    def test_equal_prefix_only(self):
        pool = StringPool()
        pool.add("abc")
        pool.add("abcd")
        self.assertFalse(pool.equal(0, 1))

    def test_equal_counts_access(self):
        pool = StringPool()
        pool.add("aaa")
        pool.add("aab")
        pool.reset_access_count()
        pool.equal(0, 1)
        self.assertGreater(pool.access_count, 0)


class TestLcp(unittest.TestCase):
    def test_lcp_common(self):
        self.assertEqual(sample().lcp(0, 1), 3)

    def test_lcp_identical(self):
        self.assertEqual(sample().lcp(0, 2), 6)

    def test_lcp_none(self):
        self.assertEqual(sample().lcp(0, 3), 0)

    def test_lcp_prefix(self):
        pool = StringPool()
        pool.add("abcd")
        pool.add("abc")
        self.assertEqual(pool.lcp(0, 1), 3)

    def test_lcp_empty_string(self):
        pool = StringPool()
        pool.add("")
        pool.add("abc")
        self.assertEqual(pool.lcp(0, 1), 0)


class TestDuplicates(unittest.TestCase):
    def test_finds_group(self):
        self.assertEqual(sample().duplicates(), [(0, 2)])

    def test_no_duplicates(self):
        pool = StringPool()
        pool.add("a")
        pool.add("b")
        self.assertEqual(pool.duplicates(), [])

    def test_groups_sorted_by_min_index(self):
        pool = StringPool()
        pool.add("x")
        pool.add("y")
        pool.add("x")
        pool.add("y")
        self.assertEqual(pool.duplicates(), [(0, 2), (1, 3)])

    def test_empty_pool(self):
        self.assertEqual(StringPool().duplicates(), [])


if __name__ == "__main__":
    unittest.main()
