"""FlatMap 现有行为的锁定测试（基线，改造期间一字不改且必须全绿）。"""

import unittest

from btreex.store import FlatMap


class TestPutGet(unittest.TestCase):
    def test_put_new_returns_true_and_overwrite_returns_false(self):
        m = FlatMap()
        self.assertTrue(m.put("b", 2))
        self.assertFalse(m.put("b", 20))
        self.assertEqual(m.get("b"), 20)
        self.assertEqual(m.size(), 1)

    def test_get_missing_default(self):
        m = FlatMap()
        m.put("a", 1)
        self.assertEqual(m.get("a"), 1)
        self.assertIsNone(m.get("zzz"))
        self.assertEqual(m.get("zzz", 0), 0)

    def test_keys_stay_sorted_after_scattered_inserts(self):
        m = FlatMap()
        for k in (5, 1, 4, 2, 3):
            m.put(k, k * 10)
        self.assertEqual(m.keys(), [1, 2, 3, 4, 5])
        self.assertEqual(m.items(), [(1, 10), (2, 20), (3, 30), (4, 40), (5, 50)])

    def test_size_and_contains(self):
        m = FlatMap()
        for k in ("c", "a", "b"):
            m.put(k, k)
        self.assertEqual(m.size(), 3)
        self.assertEqual(len(m), 3)
        self.assertIn("a", m)
        self.assertNotIn("z", m)


class TestDelete(unittest.TestCase):
    def test_delete_existing_then_missing(self):
        m = FlatMap()
        for k in ("a", "b", "c"):
            m.put(k, k)
        self.assertTrue(m.delete("b"))
        self.assertFalse(m.delete("b"))
        self.assertEqual(m.keys(), ["a", "c"])
        self.assertEqual(m.size(), 2)

    def test_delete_all_keys_leaves_empty_map(self):
        m = FlatMap()
        for k in range(4):
            m.put(k, k)
        for k in range(4):
            self.assertTrue(m.delete(k))
        self.assertEqual(m.keys(), [])
        self.assertEqual(m.size(), 0)
        self.assertIsNone(m.get(0))

    def test_delete_missing_does_not_touch_structure(self):
        m = FlatMap()
        m.put(1, "one")
        self.assertFalse(m.delete(99))
        self.assertEqual(m.items(), [(1, "one")])


class TestKeysInRange(unittest.TestCase):
    def test_inclusive_bounds(self):
        m = FlatMap()
        for i in range(5):
            m.put(i, i * 10)
        self.assertEqual(m.keys_in_range(1, 3), [(1, 10), (2, 20), (3, 30)])
        self.assertEqual(
            m.keys_in_range(0, 4),
            [(0, 0), (1, 10), (2, 20), (3, 30), (4, 40)],
        )

    def test_equal_bounds(self):
        m = FlatMap()
        m.put(5, "x")
        self.assertEqual(m.keys_in_range(5, 5), [(5, "x")])

    def test_empty_result_when_out_of_span(self):
        m = FlatMap()
        m.put(1, 1)
        m.put(2, 2)
        self.assertEqual(m.keys_in_range(3, 9), [])
        self.assertEqual(m.keys_in_range(0, 0), [])

    def test_reversed_bounds_raise(self):
        m = FlatMap()
        m.put(1, 1)
        with self.assertRaises(ValueError):
            m.keys_in_range(2, 1)

    def test_bounds_landing_between_keys(self):
        m = FlatMap()
        for k in (10, 20, 30):
            m.put(k, k)
        self.assertEqual(m.keys_in_range(11, 29), [(20, 20)])


class TestEdgeAndErrors(unittest.TestCase):
    def test_empty_map(self):
        m = FlatMap()
        self.assertEqual(m.size(), 0)
        self.assertIsNone(m.get(1))
        self.assertEqual(m.keys(), [])
        self.assertEqual(m.items(), [])

    def test_single_key(self):
        m = FlatMap()
        m.put(7, "seven")
        self.assertEqual(m.get(7), "seven")
        self.assertEqual(m.keys_in_range(7, 7), [(7, "seven")])

    def test_repeated_same_key_updates_in_place(self):
        m = FlatMap()
        for v in range(5):
            m.put("k", v)
        self.assertEqual(m.size(), 1)
        self.assertEqual(m.get("k"), 4)

    def test_illegal_key_raises(self):
        m = FlatMap()
        with self.assertRaises(ValueError):
            m.put(1.5, "x")
        with self.assertRaises(ValueError):
            m.get([1])
        with self.assertRaises(ValueError):
            m.delete(None)
        self.assertEqual(m.size(), 0)


if __name__ == "__main__":
    unittest.main()
