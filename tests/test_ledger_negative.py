"""ledger 在负数与默认 trunc 口径下的分账不变量（基线文件不动，另开）。"""

import unittest

from fixedpt import Domain, Fixed, ledger


class TestNegativeSplit(unittest.TestCase):

    def setUp(self):
        self.d = Domain(bits=64, scale=6)

    def test_negative_amount_parts_sum_exactly(self):
        for unscaled in (-10_000_000, -1, -7, -999_999, -12_345_678):
            amount = self.d.fixed(unscaled)
            for parts in (2, 3, 7):
                shares = ledger.split(self.d, amount, parts)
                self.assertEqual(len(shares), parts)
                self.assertEqual(ledger.total_of(self.d, shares), amount,
                                 (unscaled, parts))
                spread = max(p.unscaled for p in shares) - \
                    min(p.unscaled for p in shares)
                self.assertLessEqual(spread, 1)

    def test_positive_amount_unchanged_behavior(self):
        parts = ledger.split(self.d, self.d.fixed(10_000_000), 3)
        self.assertEqual([p.unscaled for p in parts],
                         [3_333_334, 3_333_333, 3_333_333])


if __name__ == "__main__":
    unittest.main()
