"""Domain.parse / Domain.text：科学计数法、多余零、精度舍入、来回稳定。"""

import unittest

from fixedpt import (
    CEIL,
    FLOOR,
    HALF_EVEN,
    TRUNC,
    UP,
    Domain,
    Fixed,
    ParseError,
)


class TestParsePlain(unittest.TestCase):

    def setUp(self):
        self.d = Domain(bits=64, scale=6)

    def test_integers(self):
        self.assertEqual(self.d.parse("0"), Fixed(0, 6))
        self.assertEqual(self.d.parse("1200"), Fixed(1_200_000_000, 6))
        self.assertEqual(self.d.parse("-7"), Fixed(-7_000_000, 6))
        self.assertEqual(self.d.parse("+7"), Fixed(7_000_000, 6))

    def test_fractional(self):
        self.assertEqual(self.d.parse("1.5"), Fixed(1_500_000, 6))
        self.assertEqual(self.d.parse("0.000001"), Fixed(1, 6))
        self.assertEqual(self.d.parse("-0.000002"), Fixed(-2, 6))
        self.assertEqual(self.d.parse(".5"), Fixed(500_000, 6))
        self.assertEqual(self.d.parse("-.5"), Fixed(-500_000, 6))
        self.assertEqual(self.d.parse("1."), Fixed(1_000_000, 6))

    def test_extra_leading_and_trailing_zeros(self):
        for text in ("1.500000", "001.5", "0001.5000", "01.50"):
            self.assertEqual(self.d.parse(text), Fixed(1_500_000, 6), text)


class TestParseScientific(unittest.TestCase):

    def setUp(self):
        self.d = Domain(bits=64, scale=6)

    def test_exponent_forms(self):
        self.assertEqual(self.d.parse("1.5e3"), Fixed(1_500_000_000, 6))
        self.assertEqual(self.d.parse("1.5E3"), Fixed(1_500_000_000, 6))
        self.assertEqual(self.d.parse("150e-2"), Fixed(1_500_000, 6))
        self.assertEqual(self.d.parse("1E-6"), Fixed(1, 6))
        self.assertEqual(self.d.parse("1e+6"), Fixed(10 ** 12, 6))
        self.assertEqual(self.d.parse("-2.5e-6"), Fixed(-2, 6))
        self.assertEqual(self.d.parse("12e2"), Fixed(1_200_000_000, 6))

    def test_extra_zeros_in_scientific(self):
        self.assertEqual(self.d.parse("001.500e3"),
                         Fixed(1_500_000_000, 6))


class TestParseRounding(unittest.TestCase):

    def setUp(self):
        self.d = Domain(bits=64, scale=2)

    def test_overlong_fraction_uses_domain_mode(self):
        d = Domain(bits=64, scale=2, rounding=HALF_EVEN)
        self.assertEqual(d.parse("1.235"), Fixed(124, 2))
        self.assertEqual(d.parse("1.245"), Fixed(124, 2))
        self.assertEqual(d.parse("-1.235"), Fixed(-124, 2))

    def test_overlong_fraction_per_call_mode(self):
        self.assertEqual(self.d.parse("1.239", rounding=TRUNC), Fixed(123, 2))
        self.assertEqual(self.d.parse("1.239", rounding=UP), Fixed(124, 2))
        self.assertEqual(self.d.parse("1.239", rounding=FLOOR), Fixed(123, 2))
        self.assertEqual(self.d.parse("1.239", rounding=CEIL), Fixed(124, 2))
        self.assertEqual(self.d.parse("-1.239", rounding=FLOOR),
                         Fixed(-124, 2))
        self.assertEqual(self.d.parse("-1.239", rounding=CEIL),
                         Fixed(-123, 2))
        self.assertEqual(self.d.parse("1.235", rounding=HALF_EVEN),
                         Fixed(124, 2))

    def test_tiny_values_round_to_zero_by_mode(self):
        self.assertEqual(self.d.parse("0.001", rounding=TRUNC), Fixed(0, 2))
        self.assertEqual(self.d.parse("0.001", rounding=UP), Fixed(1, 2))
        self.assertEqual(self.d.parse("-0.001", rounding=UP), Fixed(-1, 2))
        self.assertEqual(self.d.parse("-0.001", rounding=CEIL), Fixed(0, 2))


class TestParseErrors(unittest.TestCase):

    def setUp(self):
        self.d = Domain(bits=64, scale=6)

    def test_bad_text(self):
        for text in ("", ".", "abc", "1.2.3", "1e", "e5", "+", "-",
                     "inf", "nan", " 1.5", "1.5 ", "1,5", "0x10",
                     "1.5e", "1.5e+", "1_000"):
            with self.assertRaises(ParseError):
                self.d.parse(text)

    def test_non_string_rejected(self):
        with self.assertRaises(ParseError):
            self.d.parse(1.5)
        with self.assertRaises(ParseError):
            self.d.parse(None)


class TestParseFit(unittest.TestCase):

    def test_parse_overflow_respects_policy(self):
        from fixedpt import DomainOverflow
        d = Domain(bits=8, scale=0)
        with self.assertRaises(DomainOverflow):
            d.parse("128")
        sat = Domain(bits=8, scale=0, overflow="saturate")
        self.assertEqual(sat.parse("1e3"), Fixed(127, 0))
        self.assertEqual(sat.parse("-1e3"), Fixed(-128, 0))
        wrap = Domain(bits=8, scale=0, overflow="wrap")
        self.assertEqual(wrap.parse("128"), Fixed(-128, 0))


class TestText(unittest.TestCase):

    def setUp(self):
        self.d = Domain(bits=64, scale=6)

    def test_canonical_plain_form(self):
        cases = {
            Fixed(1_500_000, 6): "1.5",
            Fixed(10, 6): "0.00001",
            Fixed(1, 6): "0.000001",
            Fixed(1_000_000, 6): "1",
            Fixed(-2, 6): "-0.000002",
            Fixed(-1_234_567, 6): "-1.234567",
            Fixed(1_200_000_000, 6): "1200",
            Fixed(0, 6): "0",
        }
        for value, want in cases.items():
            self.assertEqual(self.d.text(value), want, repr(value))

    def test_integer_scale_zero(self):
        self.assertEqual(self.d.text(Fixed(123, 0)), "123")
        self.assertEqual(self.d.text(Fixed(-123, 0)), "-123")

    def test_other_scales(self):
        self.assertEqual(self.d.text(Fixed(12, 2)), "0.12")
        self.assertEqual(self.d.text(Fixed(-5, 2)), "-0.05")
        self.assertEqual(self.d.text(Fixed(150, 2)), "1.5")

    def test_non_fixed_rejected(self):
        from fixedpt import FixedPointError
        with self.assertRaises(FixedPointError):
            self.d.text(1.5)


class TestRoundTrip(unittest.TestCase):

    def test_text_parse_stable(self):
        d = Domain(bits=64, scale=6)
        values = [
            "0", "1", "-1", "1.5", "0.000001", "-0.000001",
            "123456.789", "-999999.999999", "1000000",
        ]
        for text in values:
            value = d.parse(text)
            again = d.parse(d.text(value))
            self.assertEqual(again, value, text)
            self.assertEqual(d.text(again), d.text(value), text)

    def test_parse_scientific_text_canonicalizes(self):
        d = Domain(bits=64, scale=6)
        self.assertEqual(d.text(d.parse("1.500e3")), "1500")
        self.assertEqual(d.text(d.parse("001.50")), "1.5")


if __name__ == "__main__":
    unittest.main()
