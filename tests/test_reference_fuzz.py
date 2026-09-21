"""对拍：随机时间戳与纯 Decimal 参考实现逐位一致性。

固定随机种子（不依赖网络/时钟），覆盖事故提到的三类输入：
负时间戳、半秒（及其他小数秒）、千年跨度。
参考实现只用 Decimal 表达 README 契约，被测代码走 stampkit 公共入口。
"""

import random
import unittest
from decimal import ROUND_FLOOR, Decimal

from stampkit import align, span, units


def _dec(value):
    """与生产代码一致：float 按十进制字面值（str）解析。"""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    return Decimal(str(value))


def ref_to_millis(value, unit):
    millis = _dec(value) if unit == "ms" else _dec(value) * 1000
    return int(millis.to_integral_value(rounding=ROUND_FLOOR))


def ref_to_seconds(value, unit):
    return _dec(value) / 1000 if unit == "ms" else _dec(value)


def ref_floor_bucket(ts_ms, interval_ms):
    return (ts_ms // interval_ms) * interval_ms


def ref_ceil_bucket(ts_ms, interval_ms):
    return -((-ts_ms) // interval_ms) * interval_ms


def ref_bucket_index(ts_ms, interval_ms):
    return ts_ms // interval_ms


def ref_bucket_span(start_ms, end_ms, interval_ms):
    if end_ms <= start_ms:
        return 0
    return ref_ceil_bucket(end_ms, interval_ms) // interval_ms - (
        start_ms // interval_ms
    )


UNIT_FACTOR_MS = {
    "ms": 1,
    "s": 1000,
    "min": 60 * 1000,
    "h": 3600 * 1000,
    "d": 86_400 * 1000,
}


def ref_duration_between(start_ms, end_ms, unit):
    return (end_ms - start_ms) // UNIT_FACTOR_MS[unit]


INTERVALS_MS = [1, 7, 100, 250, 1000, 5000, 60_000, 900_000, 3_600_000, 86_400_000]

# 秒值约 ±1000 年；毫秒值约 ±1000 年。
YEAR_S = 365 * 86_400


def _random_second_int(rng):
    return rng.randint(-1000 * YEAR_S, 1000 * YEAR_S)


def _random_millis_int(rng):
    return rng.randint(-1000 * YEAR_S * 1000, 1000 * YEAR_S * 1000)


def _random_second_float(rng):
    # 小数位固定 6 位，含半秒；整数部分覆盖千年跨度与负值。
    whole = rng.randint(-1000 * YEAR_S, 1000 * YEAR_S)
    frac = rng.randint(0, 999_999)
    sign = "-" if whole < 0 else ""
    return float("%s%d.%06d" % (sign, abs(whole), frac))


class DecimalReferenceFuzzTests(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(20260921)

    def test_units_int_seconds_and_millis(self):
        for _ in range(400):
            for value, unit in (
                (_random_second_int(self.rng), "s"),
                (_random_millis_int(self.rng), "ms"),
            ):
                self.assertEqual(units.to_millis(value, unit), ref_to_millis(value, unit))
                self.assertEqual(units.to_seconds(value, unit), ref_to_seconds(value, unit))

    def test_units_float_literals(self):
        for _ in range(400):
            value = _random_second_float(self.rng)
            self.assertEqual(units.to_millis(value, "s"), ref_to_millis(value, "s"))
            self.assertEqual(units.to_seconds(value, "s"), ref_to_seconds(value, "s"))
            millis_value = float(Decimal(str(value)) * 1000)
            self.assertEqual(
                units.to_millis(millis_value, "ms"), ref_to_millis(millis_value, "ms")
            )

    def test_units_guess_matches_threshold(self):
        for _ in range(400):
            value = self.rng.choice(
                [_random_second_int(self.rng), _random_millis_int(self.rng)]
            )
            guessed = units.guess_unit(value)
            self.assertEqual(guessed, "ms" if abs(value) >= 10**11 else "s")
            self.assertEqual(units.to_millis(value), ref_to_millis(value, guessed))

    def test_align_primitives(self):
        for _ in range(800):
            ts_ms = _random_millis_int(self.rng)
            interval_ms = self.rng.choice(INTERVALS_MS)
            self.assertEqual(
                align.floor_bucket(ts_ms, interval_ms),
                ref_floor_bucket(ts_ms, interval_ms),
            )
            self.assertEqual(
                align.ceil_bucket(ts_ms, interval_ms),
                ref_ceil_bucket(ts_ms, interval_ms),
            )
            self.assertEqual(
                align.bucket_index(ts_ms, interval_ms),
                ref_bucket_index(ts_ms, interval_ms),
            )

    def test_bucket_span_random_ranges(self):
        for _ in range(800):
            start_ms = _random_millis_int(self.rng)
            end_ms = start_ms + self.rng.randint(-2, 5) * self.rng.choice(
                INTERVALS_MS
            ) + self.rng.randint(-999, 999)
            interval_ms = self.rng.choice(INTERVALS_MS)
            self.assertEqual(
                align.bucket_span(start_ms, end_ms, interval_ms),
                ref_bucket_span(start_ms, end_ms, interval_ms),
            )

    def test_align_many_matches_reference(self):
        for _ in range(20):
            interval_ms = self.rng.choice(INTERVALS_MS)
            unit = self.rng.choice(["s", "ms"])
            if unit == "s":
                values = [_random_second_int(self.rng) for _ in range(64)]
            else:
                values = [_random_millis_int(self.rng) for _ in range(64)]
            expected = [
                ref_floor_bucket(ref_to_millis(v, unit), interval_ms) for v in values
            ]
            self.assertEqual(align.align_many(values, interval_ms, unit=unit), expected)

    def test_duration_all_units(self):
        for _ in range(600):
            start_ms = _random_millis_int(self.rng)
            end_ms = start_ms + self.rng.randint(
                -1000 * YEAR_S * 1000, 1000 * YEAR_S * 1000
            )
            unit = self.rng.choice(list(UNIT_FACTOR_MS))
            self.assertEqual(
                span.duration_between(start_ms, end_ms, unit),
                ref_duration_between(start_ms, end_ms, unit),
            )

    def test_pack_round_trip_random(self):
        for _ in range(200):
            value = self.rng.randint(-(2**63), 2**63 - 1)
            self.assertEqual(span.unpack_duration(span.pack_duration(value)), value)


if __name__ == "__main__":
    unittest.main()
