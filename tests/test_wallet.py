"""Wallet 现有行为的锁定测试：浮点余额与浮点加减。

只覆盖当前实现已经具备的能力。定点货币、货币代码、舍入模式、配比分摊、
汇率换算、格式化与解析都还没有，新增行为另建测试文件，不改动本文件。
"""

import unittest

from coinlib import Wallet


class TestBalance(unittest.TestCase):
    def test_default_balance_is_zero(self):
        self.assertEqual(Wallet().balance(), 0.0)

    def test_initial_balance_kept(self):
        self.assertEqual(Wallet(12.5).balance(), 12.5)


class TestArithmetic(unittest.TestCase):
    def test_deposit_returns_new_balance(self):
        wallet = Wallet()
        self.assertEqual(wallet.deposit(10.0), 10.0)
        self.assertEqual(wallet.balance(), 10.0)

    def test_withdraw_returns_new_balance(self):
        wallet = Wallet(10.0)
        self.assertEqual(wallet.withdraw(3.0), 7.0)
        self.assertEqual(wallet.balance(), 7.0)

    def test_sequence_of_ops(self):
        wallet = Wallet(100.0)
        wallet.deposit(20.0)
        wallet.withdraw(50.0)
        wallet.deposit(5.0)
        self.assertEqual(wallet.balance(), 75.0)

    def test_balance_is_float(self):
        self.assertIsInstance(Wallet(1).balance(), float)


class TestBaselineLimits(unittest.TestCase):
    """基线实现是浮点的，这里把当前真实取值锁住，供改造后对照。"""

    def test_float_drift_is_visible(self):
        wallet = Wallet()
        wallet.deposit(0.1)
        wallet.deposit(0.2)
        self.assertNotEqual(wallet.balance(), 0.3)
        self.assertEqual(wallet.balance(), 0.1 + 0.2)

    def test_no_currency_concept(self):
        wallet = Wallet()
        self.assertFalse(hasattr(wallet, "currency"))

    def test_repr(self):
        self.assertEqual(repr(Wallet(2.5)), "Wallet(balance=2.5)")


if __name__ == "__main__":
    unittest.main()
