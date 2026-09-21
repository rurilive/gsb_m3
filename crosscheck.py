"""随机对拍：stampkit 实现 vs 纯 Decimal 参考实现。

覆盖负时间戳、半秒/任意小数位字面量、千年跨度、亚秒桶与显式单位。
用法：python3 crosscheck.py
"""

import random
import struct
from decimal import ROUND_FLOOR, Decimal

from stampkit import align, span, units

THOUSAND = Decimal(1000)
GUESS_THRESHOLD = 10**11


def ref_literal(value):
    if isinstance(value, int):
        return Decimal(value)
    return Decimal(repr(float(value)))


def ref_guess(value):
    return "ms" if abs(value) >= GUESS_THRESHOLD else "s"


def ref_to_millis(value, unit):
    unit = unit or ref_guess(value)
    dec = ref_literal(value)
    if unit == "s":
        dec = dec * THOUSAND
    return int(dec.to_integral_value(rounding=ROUND_FLOOR))


def ref_to_seconds(value, unit):
    unit = unit or ref_guess(value)
    dec = ref_literal(value)
    return dec.scaleb(-3) if unit == "ms" else dec


def ref_floor(ts_ms, interval_ms):
    return (ts_ms // interval_ms) * interval_ms


def ref_ceil(ts_ms, interval_ms):
    floor_value, remainder = divmod(ts_ms, interval_ms)
    return floor_value * interval_ms if remainder == 0 else (floor_value + 1) * interval_ms


def ref_span(start_ms, end_ms, interval_ms):
    if end_ms <= start_ms:
        return 0
    return (end_ms - 1) // interval_ms - start_ms // interval_ms + 1


def ref_duration(start_ms, end_ms, factor_ms):
    return (end_ms - start_ms) // factor_ms


UNITS = ["s", "ms", None]
INTERVALS_MS = [1, 2, 7, 100, 250, 1000, 60_000, 3_600_000, 86_400_000]
DURATION_FACTORS = {
    "ms": 1,
    "s": 1000,
    "min": 60_000,
    "h": 3_600_000,
    "d": 86_400_000,
}


def random_int_timestamp(rng):
    millennium_ms = 1000 * 365 * 86_400_000
    return rng.randint(-millennium_ms, millennium_ms)


def random_scalar(rng):
    kind = rng.randrange(9)
    if kind < 4:
        return random_int_timestamp(rng)
    if kind == 4:
        return rng.choice([0.5, -0.5, 1.5, -1.5])
    if kind == 5:
        return rng.randint(-10**10, 10**10) / 1000.0
    if kind == 6:
        return rng.randint(-10**13, 10**13) / 1000.0
    if kind == 7:
        return rng.randint(-10**16, 10**16) / 1000.0
    return float(rng.randint(-10**12, 10**12))


def main():
    rng = random.Random(20260921)
    iterations = 200_000

    for _ in range(iterations):
        value = random_scalar(rng)
        unit = rng.choice(UNITS)

        got_ms = units.to_millis(value, unit)
        ref_ms = ref_to_millis(value, unit)
        assert got_ms == ref_ms and isinstance(got_ms, int), (value, unit, got_ms, ref_ms)

        got_s = units.to_seconds(value, unit)
        ref_s = ref_to_seconds(value, unit)
        assert got_s == ref_s and isinstance(got_s, Decimal), (value, unit, got_s, ref_s)

        ts_ms = ref_ms
        interval_ms = rng.choice(INTERVALS_MS)

        assert align.floor_bucket(ts_ms, interval_ms) == ref_floor(ts_ms, interval_ms)
        assert align.ceil_bucket(ts_ms, interval_ms) == ref_ceil(ts_ms, interval_ms)
        assert align.bucket_index(ts_ms, interval_ms) == ts_ms // interval_ms

        start_ms = rng.randint(-3 * 365 * 86_400_000, 3 * 365 * 86_400_000)
        end_ms = start_ms + rng.randint(-2 * 86_400_000, 2 * 86_400_000)
        assert align.bucket_span(start_ms, end_ms, interval_ms) == ref_span(
            start_ms, end_ms, interval_ms
        )

        duration_unit = rng.choice(list(DURATION_FACTORS))
        assert span.duration_between(start_ms, end_ms, duration_unit) == ref_duration(
            start_ms, end_ms, DURATION_FACTORS[duration_unit]
        )

    # align_many 逐条等价性：混合 int/float、混合单位与猜测。
    for unit in UNITS:
        values = [random_scalar(rng) for _ in range(5_000)]
        interval_ms = rng.choice(INTERVALS_MS)
        expected = [ref_floor(ref_to_millis(v, unit), interval_ms) for v in values]
        assert align.align_many(values, interval_ms, unit) == expected

    # 归档编码对拍（含 int64 边界与千年跨度）。
    edge_ms = [0, 1, -1, 2**63 - 1, -(2**63), 1000 * 365 * 86_400_000, -99 * 365 * 86_400_000]
    for ms in edge_ms:
        blob = span.pack_duration(ms)
        assert blob == struct.pack("<q", ms) and len(blob) == 8
        assert span.unpack_duration(blob) == ms

    print("crosscheck ok: %d randomized iterations + align_many equivalence" % iterations)


if __name__ == "__main__":
    main()
