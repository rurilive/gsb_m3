"""事故复盘锁死用例：单位判定、十进制字面值换算与取整方向。

这些用例固定 README 契约，基线文件 tests/test_units.py 不做改动。
"""

import unittest
from decimal import Decimal

from stampkit import units


class GuessThresholdTests(unittest.TestCase):
    def test_boundary_is_10_pow_11(self):
        # 契约：abs(value) >= 10**11 判毫秒，否则判秒。
        self.assertEqual(units.guess_unit(99_999_999_999), "s")
        self.assertEqual(units.guess_unit(100_000_000_000), "ms")
        self.assertEqual(units.guess_unit(-99_999_999_999), "s")
        self.assertEqual(units.guess_unit(-100_000_000_000), "ms")

    def test_thirteen_digit_millis(self):
        # 十三位毫秒时间戳（1.7e12）必须判毫秒，十位秒时间戳必须判秒。
        self.assertEqual(units.guess_unit(1_700_000_000_000), "ms")
        self.assertEqual(units.guess_unit(1_700_000_000), "s")
        self.assertEqual(units.guess_unit(-1_700_000_000_000), "ms")


class ExplicitUnitWinsTests(unittest.TestCase):
    def test_small_value_forced_as_millis(self):
        # 1500 按启发式会判秒；显式 ms 不许被翻盘。
        self.assertEqual(units.to_millis(1500, unit="ms"), 1500)
        self.assertEqual(units.to_seconds(1500, unit="ms"), Decimal("1.5"))

    def test_large_value_forced_as_seconds(self):
        # 十三位数字按启发式会判毫秒；显式 s 必须放大一千倍。
        self.assertEqual(
            units.to_millis(1_700_000_000_000, unit="s"),
            1_700_000_000_000_000,
        )
        self.assertEqual(
            units.to_seconds(1_700_000_000_000, unit="s"),
            Decimal("1700000000000"),
        )

    def test_explicit_unit_applies_every_call(self):
        for value in (0, 1, 99_999_999_999, 1_700_000_000_000):
            self.assertEqual(units.to_millis(value, unit="ms"), value)


class DecimalLiteralTests(unittest.TestCase):
    def test_half_second_rounds_down(self):
        self.assertEqual(units.to_millis(0.5, unit="s"), 500)
        self.assertEqual(units.to_millis(1_700_000_000.5, unit="s"), 1_700_000_000_500)

    def test_negative_half_second_floors_toward_minus_infinity(self):
        # -0.5s = -500ms 恰好整；-0.0005s 必须落到 -1ms，而不是 0。
        self.assertEqual(units.to_millis(-0.5, unit="s"), -500)
        self.assertEqual(units.to_millis(-0.0005, unit="s"), -1)
        self.assertEqual(units.to_millis(-1.0005, unit="s"), -1_001)

    def test_float_millis_floors(self):
        self.assertEqual(units.to_millis(0.4, unit="ms"), 0)
        self.assertEqual(units.to_millis(-0.4, unit="ms"), -1)
        self.assertEqual(units.to_millis(-1.5, unit="ms"), -2)

    def test_binary_float_noise_not_used(self):
        # 0.1 + 0.2 在二进制浮点里不是 0.3；按十进制字面值必须得 300ms。
        self.assertEqual(units.to_millis(0.1 + 0.2, unit="s"), 300)

    def test_to_seconds_is_exact_decimal(self):
        self.assertEqual(units.to_seconds(0.5, unit="s"), Decimal("0.5"))
        self.assertEqual(units.to_seconds(-0.0005, unit="s"), Decimal("-0.0005"))
        self.assertEqual(units.to_seconds(500, unit="ms"), Decimal("0.5"))
        self.assertEqual(units.to_seconds(-1, unit="ms"), Decimal("-0.001"))

    def test_integer_inputs_stay_on_integer_path(self):
        # int 乘 1000 精确，千年跨度也不能有浮点误差。
        millennium_seconds = 1000 * 365 * 86_400
        self.assertEqual(
            units.to_millis(millennium_seconds, unit="s"),
            millennium_seconds * 1000,
        )
        self.assertIsInstance(units.to_millis(1_700_000_000, unit="s"), int)


if __name__ == "__main__":
    unittest.main()
