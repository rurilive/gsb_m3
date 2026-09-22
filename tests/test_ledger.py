"""ledger 行为基线：累加、计息、分账的精确性与对账。"""

import unittest

from fixedpt import Domain, Fixed, FixedPointError, ledger


class TestLedger(unittest.TestCase):

    def setUp(self):
        self.d = Domain(bits=64, scale=6)

    def test_total_of_sums_entries(self):
        values = [
            self.d.fixed(1_500_000),       # 1.50
            self.d.fixed(2_250_000),       # 2.25
            self.d.fixed(-750_000),        # -0.75
        ]
        self.assertEqual(ledger.total_of(self.d, values), self.d.fixed(3_000_000))

    def test_total_of_empty_is_zero(self):
        self.assertEqual(ledger.total_of(self.d, []), self.d.fixed(0))

    def test_apply_rate(self):
        amount = self.d.fixed(120_000_000)   # 120.00
        rate = Fixed(33333, 6)               # 0.033333
        self.assertEqual(
            ledger.apply_rate(self.d, amount, rate, out_scale=6),
            self.d.fixed(3_999_960))         # 3.999960

    def test_split_sums_exactly(self):
        amount = self.d.fixed(10_000_000)    # 10.00
        parts = ledger.split(self.d, amount, 3)
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0].unscaled, 3_333_334)
        self.assertEqual(parts[1].unscaled, 3_333_333)
        self.assertEqual(parts[2].unscaled, 3_333_333)
        self.assertEqual(ledger.total_of(self.d, parts), amount)

    def test_split_even_amount(self):
        amount = self.d.fixed(9_000_000)     # 9.00
        parts = ledger.split(self.d, amount, 3)
        self.assertEqual([p.unscaled for p in parts], [3_000_000] * 3)

    def test_split_rejects_bad_parts(self):
        with self.assertRaises(FixedPointError):
            ledger.split(self.d, self.d.fixed(100), 0)
        with self.assertRaises(FixedPointError):
            ledger.split(self.d, self.d.fixed(100), -2)

    def test_reconcile(self):
        diff = ledger.reconcile(
            self.d, [self.d.fixed(150_000), self.d.fixed(-50_000)],
            self.d.fixed(100_000))
        self.assertEqual(diff, self.d.fixed(0))


if __name__ == "__main__":
    unittest.main()
