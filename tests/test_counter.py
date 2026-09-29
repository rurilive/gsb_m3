"""QuotaCounter 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：上限校验、check 只读、add 累加、
超限时抛 QuotaExceeded 且不改动已用量、remaining 口径与非法入参拒绝。
新增行为（层级配额、两阶段预留、借用、超时回收、并发）另建测试文件，
不改动本文件。
"""

import unittest

from quotactl.counter import QuotaCounter, QuotaError, QuotaExceeded


class TestConstruct(unittest.TestCase):
    def test_initial_state(self):
        c = QuotaCounter(10)
        self.assertEqual(c.limit, 10)
        self.assertEqual(c.used, 0)
        self.assertEqual(c.remaining, 10)

    def test_zero_limit_rejected(self):
        with self.assertRaises(ValueError):
            QuotaCounter(0)

    def test_negative_limit_rejected(self):
        with self.assertRaises(ValueError):
            QuotaCounter(-5)

    def test_non_int_limit_rejected(self):
        with self.assertRaises(TypeError):
            QuotaCounter(3.5)


class TestCheck(unittest.TestCase):
    def test_check_does_not_mutate(self):
        c = QuotaCounter(10)
        self.assertTrue(c.check(10))
        self.assertEqual(c.used, 0)

    def test_check_over_limit_is_false(self):
        c = QuotaCounter(10)
        self.assertFalse(c.check(11))

    def test_check_zero_is_true(self):
        c = QuotaCounter(10)
        self.assertTrue(c.check(0))


class TestAdd(unittest.TestCase):
    def test_add_accumulates(self):
        c = QuotaCounter(10)
        self.assertEqual(c.add(4), 4)
        self.assertEqual(c.add(6), 10)
        self.assertEqual(c.used, 10)
        self.assertEqual(c.remaining, 0)

    def test_add_over_limit_raises_and_leaves_state(self):
        c = QuotaCounter(10)
        c.add(7)
        with self.assertRaises(QuotaExceeded):
            c.add(4)
        self.assertEqual(c.used, 7)
        self.assertEqual(c.remaining, 3)

    def test_exceeded_exception_is_quota_error(self):
        c = QuotaCounter(1)
        with self.assertRaises(QuotaError):
            c.add(2)

    def test_negative_amount_rejected(self):
        c = QuotaCounter(10)
        with self.assertRaises(ValueError):
            c.add(-1)
        self.assertEqual(c.used, 0)

    def test_bool_amount_rejected(self):
        c = QuotaCounter(10)
        with self.assertRaises(TypeError):
            c.add(True)


if __name__ == "__main__":
    unittest.main()
