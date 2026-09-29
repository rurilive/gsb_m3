"""基线行为测试：锁住 ExactSet 的精确成员语义。

这个文件是行为基线，改造后必须一字不改且保持全绿。
"""

import unittest

from bloomx import ExactSet
from bloomx.member import ExactSet as ExactSetModule


class TestExactSetBaseline(unittest.TestCase):
    def test_empty_set_contains_nothing(self):
        s = ExactSet()
        self.assertEqual(s.size(), 0)
        self.assertEqual(len(s), 0)
        self.assertFalse(s.contains("any"))
        self.assertFalse(s.contains(0))

    def test_add_then_contains(self):
        s = ExactSet()
        s.add("alpha")
        self.assertTrue(s.contains("alpha"))
        self.assertEqual(s.size(), 1)
        self.assertEqual(len(s), 1)

    def test_no_false_negative_and_no_false_positive(self):
        s = ExactSet()
        members = [f"user-{i}" for i in range(500)]
        for m in members:
            s.add(m)
        for m in members:
            self.assertTrue(s.contains(m))
        for i in range(500, 800):
            self.assertFalse(s.contains(f"user-{i}"))
        self.assertEqual(s.size(), 500)

    def test_duplicate_add_is_idempotent(self):
        s = ExactSet()
        for _ in range(10):
            s.add("dup")
        self.assertEqual(s.size(), 1)
        self.assertTrue(s.contains("dup"))

    def test_dict_reexport_identity(self):
        self.assertIs(ExactSet, ExactSetModule)

    def test_contains_does_not_mutate(self):
        s = ExactSet()
        s.add("keep")
        for _ in range(5):
            s.contains("missing")
        self.assertEqual(s.size(), 1)
        self.assertFalse(s.contains("missing"))


if __name__ == "__main__":
    unittest.main()
