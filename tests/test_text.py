"""Domain.parse 与 Domain.text：文本互转、科学计数法、精度舍入与稳定性。"""

import unittest

from fixedpt import Domain, DomainOverflow, Fixed, FixedPointError, ParseError


class TestParse(unittest.TestCase):

    def setUp(self):
        self.d = Domain(bits=64, scale=6)

    def test_plain_decimals(self):
        self.assertEqual(self.d.parse("12.34"), Fixed(12_340_000, 6))
        self.assertEqual(self.d.parse("-0.5"), Fixed(-500_000, 6))
        self.assertEqual(self.d.parse("+7"), Fixed(7_000_000, 6))
        self.assertEqual(self.d.parse("7."), Fixed(7_000_000, 6))
        self.assertEqual(self.d.parse(".5"), Fixed(500_000, 6))
        self.assertEqual(self.d.parse("-.5"), Fixed(-500_000, 6))
        self.assertEqual(self.d.parse("0"), Fixed(0, 6))
        self.assertEqual(self.d.parse("-0"), Fixed(0, 6))

    def test_extra_zeros_and_whitespace(self):
        self.assertEqual(self.d.parse("0012.3400"), Fixed(12_340_000, 6))
        self.assertEqual(self.d.parse("  12.5  "), Fixed(12_500_000, 6))
        self.assertEqual(self.d.parse("000"), Fixed(0, 6))
        self.assertEqual(self.d.parse("0.0000001"), Fixed(0, 6))

    def test_scientific_notation(self):
        self.assertEqual(self.d.parse("1.2e3"), Fixed(1_200_000_000, 6))
        self.assertEqual(self.d.parse("1.2E-3"), Fixed(1_200, 6))
        self.assertEqual(self.d.parse("5e2"), Fixed(500_000_000, 6))
        self.assertEqual(self.d.parse("-2.5e+1"), Fixed(-25_000_000, 6))
        self.assertEqual(self.d.parse("1e0"), Fixed(1_000_000, 6))
        self.assertEqual(self.d.parse("0e99"), Fixed(0, 6))

    def test_long_fraction_truncates_by_default(self):
        d = Domain(bits=64, scale=2)
        self.assertEqual(d.parse("1.005"), Fixed(100, 2))
        self.assertEqual(d.parse("1.009"), Fixed(100, 2))
        self.assertEqual(d.parse("-1.009"), Fixed(-100, 2))
        self.assertEqual(d.parse("3.14159265"), Fixed(314, 2))

    def test_long_fraction_rounds_by_mode(self):
        cases = {
            "truncate": (Fixed(100, 2), Fixed(-100, 2)),
            "ceil": (Fixed(101, 2), Fixed(-100, 2)),
            "floor": (Fixed(100, 2), Fixed(-101, 2)),
            "away": (Fixed(101, 2), Fixed(-101, 2)),
            "half_even": (Fixed(100, 2), Fixed(-100, 2)),
        }
        for mode, (pos, neg) in cases.items():
            d = Domain(bits=64, scale=2, rounding=mode)
            self.assertEqual(d.parse("1.005"), pos, mode)
            self.assertEqual(d.parse("-1.005"), neg, mode)

    def test_half_even_tie_picks_even(self):
        d = Domain(bits=64, scale=2, rounding="half_even")
        self.assertEqual(d.parse("1.015"), Fixed(102, 2))   # 1.01|5 -> 1.02
        self.assertEqual(d.parse("1.025"), Fixed(102, 2))   # 1.02|5 -> 1.02
        self.assertEqual(d.parse("-1.015"), Fixed(-102, 2))
        self.assertEqual(d.parse("-1.025"), Fixed(-102, 2))

    def test_per_call_rounding_override(self):
        d = Domain(bits=64, scale=2)
        self.assertEqual(d.parse("1.005", rounding="ceil"), Fixed(101, 2))
        self.assertEqual(d.parse("1.005"), Fixed(100, 2))

    def test_explicit_scale(self):
        self.assertEqual(self.d.parse("1.5", scale=0), Fixed(1, 0))
        self.assertEqual(self.d.parse("1.5", scale=2), Fixed(150, 2))
        with self.assertRaises(FixedPointError):
            self.d.parse("1.5", scale=-1)

    def test_invalid_text_raises_parse_error(self):
        for bad in ("", "abc", "1.2.3", "e5", "1e", "--1", "1,5", ".", "+",
                    "1.2e1.5", "0x10", "1 2", "12%", None, 12, 1.5):
            with self.assertRaises(ParseError, msg=repr(bad)):
                self.d.parse(bad)

    def test_absurd_exponent_rejected(self):
        with self.assertRaises(ParseError):
            self.d.parse("1e100001")
        with self.assertRaises(ParseError):
            self.d.parse("1e-100001")

    def test_overflow_policy_applies(self):
        small = Domain(bits=8, scale=0)
        self.assertEqual(small.parse("127"), Fixed(127, 0))
        self.assertEqual(small.parse("-128"), Fixed(-128, 0))
        with self.assertRaises(DomainOverflow):
            small.parse("128")
        sat = Domain(bits=8, scale=0, overflow="saturate")
        self.assertEqual(sat.parse("9999"), Fixed(127, 0))
        self.assertEqual(sat.parse("-9999"), Fixed(-128, 0))
        wrap = Domain(bits=8, scale=0, overflow="wrap")
        self.assertEqual(wrap.parse("128"), Fixed(-128, 0))


class TestText(unittest.TestCase):

    def setUp(self):
        self.d = Domain(bits=64, scale=6)

    def test_basic_formatting(self):
        self.assertEqual(self.d.text(Fixed(12_340_000, 6)), "12.34")
        self.assertEqual(self.d.text(Fixed(120_500_000, 6)), "120.5")
        self.assertEqual(self.d.text(Fixed(-500_000, 6)), "-0.5")
        self.assertEqual(self.d.text(Fixed(0, 6)), "0")
        self.assertEqual(self.d.text(Fixed(1, 6)), "0.000001")
        self.assertEqual(self.d.text(Fixed(-1, 6)), "-0.000001")
        self.assertEqual(self.d.text(Fixed(7_000_000, 6)), "7")
        self.assertEqual(self.d.text(Fixed(42, 0)), "42")
        self.assertEqual(self.d.text(Fixed(-42, 0)), "-42")

    def test_rejects_non_fixed(self):
        with self.assertRaises(FixedPointError):
            self.d.text("12.34")
        with self.assertRaises(FixedPointError):
            self.d.text(12)

    def test_round_trip_domain_values(self):
        values = [
            self.d.fixed(0), self.d.fixed(1), self.d.fixed(-1),
            self.d.fixed(12_340_000), self.d.fixed(-9_999_999),
            self.d.fixed(2 ** 63 - 1), self.d.fixed(-(2 ** 63)),
        ]
        for value in values:
            back = self.d.parse(self.d.text(value))
            self.assertEqual(back, value, self.d.text(value))
            self.assertEqual(back.scale, value.scale)

    def test_text_is_stable_through_parse(self):
        for raw in ("12.3400", "001.5", "1.2e3", "-.5", "0.0000001", "7."):
            once = self.d.text(self.d.parse(raw))
            twice = self.d.text(self.d.parse(once))
            self.assertEqual(once, twice, raw)


if __name__ == "__main__":
    unittest.main()
