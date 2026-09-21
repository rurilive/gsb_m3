"""BPlusTree 现有行为的锁定测试。"""

import random
import unittest

from ordix import BPlusTree, InvariantError


class TestBasicOps(unittest.TestCase):
    def test_put_get(self):
        t = BPlusTree(min_degree=2)
        self.assertTrue(t.put(10, "a"))
        self.assertFalse(t.put(10, "b"))
        self.assertEqual(t.get(10), "b")
        self.assertIsNone(t.get(11))
        self.assertEqual(len(t), 1)

    def test_empty_tree(self):
        t = BPlusTree(min_degree=2)
        self.assertIsNone(t.get(1))
        self.assertEqual(list(t.scan()), [])
        self.assertEqual(t.height(), 1)
        self.assertEqual(len(t), 0)
        self.assertFalse(t.delete(1))

    def test_keys_are_ordered(self):
        t = BPlusTree(min_degree=2)
        for k in [5, 3, 9, 1, 7, 2, 8, 0, 6, 4]:
            t.put(k, k * 10)
        self.assertEqual([k for k, _ in t.scan()], list(range(10)))
        self.assertEqual(t.get(4), 40)
        t.validate()

    def test_scan_bounds_are_half_open(self):
        t = BPlusTree(min_degree=2)
        for k in range(20):
            t.put(k, k)
        self.assertEqual([k for k, _ in t.scan(5, 9)], [5, 6, 7, 8])
        self.assertEqual([k for k, _ in t.scan(18)], [18, 19])
        self.assertEqual([k for k, _ in t.scan(stop=3)], [0, 1, 2])
        self.assertEqual([k for k, _ in t.scan(100)], [])

    def test_scan_is_lazy(self):
        t = BPlusTree(min_degree=2)
        for k in range(50):
            t.put(k, k)
        it = t.scan()
        self.assertEqual(next(it), (0, 0))
        self.assertEqual(next(it), (1, 1))
        # 没消费完就把迭代器丢掉，之后树照常用
        del it
        t.put(100, 100)
        t.delete(3)
        self.assertEqual(len(list(t.scan())), len(t))
        t.validate()


class TestStructure(unittest.TestCase):
    def test_split_produces_expected_height(self):
        t = BPlusTree(min_degree=2)
        for k in range(64):
            t.put(k, k)
        self.assertGreaterEqual(t.height(), 4)
        self.assertEqual(len(t), 64)
        t.validate()

    def test_ascending_and_descending_load(self):
        asc = BPlusTree(min_degree=2)
        desc = BPlusTree(min_degree=2)
        keys = list(range(200))
        for k in keys:
            asc.put(k, k)
        for k in reversed(keys):
            desc.put(k, k)
        asc.validate()
        desc.validate()
        self.assertEqual([k for k, _ in asc.scan()], keys)
        self.assertEqual([k for k, _ in desc.scan()], keys)
        self.assertGreaterEqual(asc.height(), 3)
        self.assertGreaterEqual(desc.height(), 3)

    def test_delete_missing_key_is_noop(self):
        t = BPlusTree(min_degree=2)
        for k in range(20):
            t.put(k, k)
        before = t.stats()
        self.assertFalse(t.delete(999))
        self.assertFalse(t.delete(-1))
        self.assertEqual(len(t), 20)
        self.assertEqual(t.stats()["removed"], before["removed"])
        t.validate()

    def test_delete_then_borrow_and_merge(self):
        t = BPlusTree(min_degree=2)
        for k in range(120):
            t.put(k, k)
        for k in range(100):
            self.assertTrue(t.delete(k))
        t.validate()
        self.assertEqual([k for k, _ in t.scan()], list(range(100, 120)))
        s = t.stats()
        self.assertGreater(s["merges"], 0)
        self.assertGreater(s["borrows"] + s["merges"], 0)

    def test_delete_all_shrinks_to_empty(self):
        t = BPlusTree(min_degree=2)
        for k in range(64):
            t.put(k, k)
        for k in range(64):
            self.assertTrue(t.delete(k))
        self.assertEqual(len(t), 0)
        self.assertEqual(t.height(), 1)
        self.assertIsNone(t.get(0))
        t.validate()

    def test_root_collapse(self):
        t = BPlusTree(min_degree=2)
        for k in range(40):
            t.put(k, k)
        tall = t.height()
        for k in range(39):
            t.delete(k)
        self.assertEqual(len(t), 1)
        self.assertEqual(t.get(39), 39)
        self.assertLess(t.height(), tall)
        t.validate()

    def test_overwrite_many_times(self):
        t = BPlusTree(min_degree=2)
        for _ in range(5):
            for k in range(30):
                t.put(k, k * 2)
        self.assertEqual(len(t), 30)
        self.assertEqual(t.get(7), 14)
        t.validate()


class TestPoolAccounting(unittest.TestCase):
    def test_nodes_are_recycled(self):
        t = BPlusTree(min_degree=2)
        for k in range(300):
            t.put(k, k)
        built = t.pool_stats()
        self.assertGreater(built["live"], 3)
        for k in range(300):
            t.delete(k)
        self.assertEqual(t.pool_stats()["live"], 1)  # 只剩根叶
        for k in range(300):
            t.put(k, k)
        again = t.pool_stats()
        self.assertEqual(again["created"], built["created"])  # 一个都没新造
        self.assertEqual(again["live"], built["live"])
        self.assertGreater(again["reused"], 10)
        t.validate()

    def test_no_leak_across_random_workload(self):
        t = BPlusTree(min_degree=3)
        model = {}

        def churn(seed):
            rnd = random.Random(seed)
            for step in range(3000):
                k = rnd.randrange(300)
                if rnd.random() < 0.6:
                    t.put(k, (k, step))
                    model[k] = (k, step)
                else:
                    t.delete(k)
                    model.pop(k, None)

        churn(7)
        # 键空间固定，节点数不该随写入次数一路涨
        bound = 2 * (len(t) // t.min_keys + 2)
        self.assertLessEqual(t.pool_stats()["live"], bound)
        churn(11)
        self.assertLessEqual(t.pool_stats()["live"], bound)
        t.validate()
        self.assertEqual([k for k, _ in t.scan()], sorted(model))
        for k, v in model.items():
            self.assertEqual(t.get(k), v)


class TestValidateDetectsDamage(unittest.TestCase):
    def test_sorted_keys(self):
        t = BPlusTree(min_degree=2)
        for k in range(50):
            t.put(k, k)
        leaf = t.root
        while not leaf.is_leaf:
            leaf = leaf.children[0]
        leaf.keys.reverse()
        with self.assertRaises(InvariantError):
            t.validate()


if __name__ == "__main__":
    unittest.main()
