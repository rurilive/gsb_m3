"""DistinctCounter 现有行为的锁定测试。"""

import threading
import unittest

from radixest.counting import DistinctCounter


class TestDistinctCounter(unittest.TestCase):
    def test_first_add_returns_true_repeat_returns_false(self):
        c = DistinctCounter()
        self.assertTrue(c.add("u1"))
        self.assertFalse(c.add("u1"))

    def test_count_counts_distinct_keys_only(self):
        c = DistinctCounter()
        for key in ["u1", "u2", "u1", "u3", "u2", "u1"]:
            c.add(key)
        self.assertEqual(c.count(), 3)

    def test_empty_counter_counts_zero(self):
        self.assertEqual(DistinctCounter().count(), 0)

    def test_keys_follow_set_equality(self):
        c = DistinctCounter()
        c.add(1)
        c.add(1.0)          # 与 1 相等，算同一个 key
        self.assertEqual(c.count(), 1)
        c.add("1")
        c.add(b"1")
        c.add((1,))
        self.assertEqual(c.count(), 4)

    def test_accepts_hashable_key_types(self):
        c = DistinctCounter()
        c.add("id-1")
        c.add(b"id-1")
        c.add((1, 2))
        c.add(None)
        self.assertEqual(c.count(), 4)

    def test_contains_reflects_added_keys(self):
        c = DistinctCounter()
        c.add("u1")
        self.assertIn("u1", c)
        self.assertNotIn("u2", c)

    def test_contains_does_not_change_count(self):
        c = DistinctCounter()
        c.add("u1")
        self.assertNotIn("nope", c)
        self.assertEqual(c.count(), 1)

    def test_reset_clears_state(self):
        c = DistinctCounter()
        c.add("u1")
        c.add("u2")
        c.reset()
        self.assertEqual(c.count(), 0)
        self.assertNotIn("u1", c)
        self.assertTrue(c.add("u1"))

    def test_add_after_reset_counts_again(self):
        c = DistinctCounter()
        c.add("u1")
        c.reset()
        c.add("u1")
        self.assertEqual(c.count(), 1)

    def test_large_sequential_input_stays_exact(self):
        c = DistinctCounter()
        for i in range(5000):
            self.assertTrue(c.add(i))
        self.assertEqual(c.count(), 5000)
        for i in range(5000):
            self.assertFalse(c.add(i))
        self.assertEqual(c.count(), 5000)

    def test_unhashable_key_raises(self):
        c = DistinctCounter()
        with self.assertRaises(TypeError):
            c.add(["not", "hashable"])

    def test_concurrent_adds_do_not_lose_keys(self):
        c = DistinctCounter()

        def worker(base):
            for i in range(200):
                c.add((base, i))

        threads = [threading.Thread(target=worker, args=(b,)) for b in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(c.count(), 800)


if __name__ == "__main__":
    unittest.main()
