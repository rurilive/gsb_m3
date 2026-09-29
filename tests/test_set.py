"""基线行为测试：锁住 ExactBag 的精确成员语义。

这个文件是行为基线，改造后必须一字不改且保持全绿。
"""

import unittest

from cuckoox import ExactBag
from cuckoox.set import ExactBag as ExactBagModule


class TestExactBagBaseline(unittest.TestCase):
    def test_empty_bag_contains_nothing(self):
        bag = ExactBag()
        self.assertEqual(bag.size(), 0)
        self.assertEqual(len(bag), 0)
        self.assertFalse(bag.contains("any"))
        self.assertFalse(bag.contains(0))

    def test_add_then_contains(self):
        bag = ExactBag()
        bag.add("alpha")
        self.assertTrue(bag.contains("alpha"))
        self.assertEqual(bag.size(), 1)
        self.assertEqual(len(bag), 1)

    def test_no_false_negative_and_no_false_positive(self):
        bag = ExactBag()
        members = ["item-{0}".format(i) for i in range(500)]
        for m in members:
            bag.add(m)
        for m in members:
            self.assertTrue(bag.contains(m))
        for i in range(500, 800):
            self.assertFalse(bag.contains("item-{0}".format(i)))
        self.assertEqual(bag.size(), 500)

    def test_duplicate_add_is_idempotent(self):
        bag = ExactBag()
        for _ in range(10):
            bag.add("dup")
        self.assertEqual(bag.size(), 1)
        self.assertTrue(bag.contains("dup"))

    def test_discard_removes_and_missing_is_silent(self):
        bag = ExactBag()
        bag.add("keep")
        bag.add("drop")
        bag.discard("drop")
        self.assertFalse(bag.contains("drop"))
        self.assertTrue(bag.contains("keep"))
        self.assertEqual(bag.size(), 1)
        # 删除从未插入的元素不报错，也不改变大小
        bag.discard("never-added")
        self.assertEqual(bag.size(), 1)

    def test_add_discard_same_item_repeatedly(self):
        bag = ExactBag()
        for _ in range(50):
            bag.add("flip")
            bag.discard("flip")
        self.assertEqual(bag.size(), 0)
        self.assertFalse(bag.contains("flip"))

    def test_reexport_identity(self):
        self.assertIs(ExactBag, ExactBagModule)

    def test_contains_does_not_mutate(self):
        bag = ExactBag()
        bag.add("keep")
        for _ in range(5):
            bag.contains("missing")
        self.assertEqual(bag.size(), 1)
        self.assertFalse(bag.contains("missing"))


if __name__ == "__main__":
    unittest.main()
