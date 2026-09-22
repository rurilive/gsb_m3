"""对拍与性能：以 fractions.Fraction 为参考，随机小数与随机运算序列逐一核对。

参考实现只依赖 Fraction 的精确算术与 math.floor，和被测代码不共享
任何舍入逻辑；边界与极限值单独造。性能门槛：百万次乘除十五秒内。
"""

import math
import random
import time
import unittest
from fractions import Fraction

from fixedpt import Domain, Fixed
from fixedpt.rounding import MODES


def ref_round_to_int(frac, mode):
    """把精确分数按模式取整，参考实现。"""
    floor = math.floor(frac)
    rem = frac - floor
    if rem == 0 or mode == "floor":
        return floor
    if mode == "ceil":
        return floor + 1
    if mode == "truncate":
        return floor + 1 if frac < 0 else floor
    if mode == "away":
        return floor if frac < 0 else floor + 1
    assert mode == "half_even", mode
    half = Fraction(1, 2)
    if rem > half or (rem == half and floor % 2):
        return floor + 1
    return floor


def ref_fit(unscaled, domain):
    """按域的 overflow 策略收口，参考实现。"""
    if domain.min_unscaled <= unscaled <= domain.max_unscaled:
        return unscaled
    if domain.overflow == "saturate":
        return max(domain.min_unscaled, min(domain.max_unscaled, unscaled))
    if domain.overflow == "wrap":
        width = domain.max_unscaled - domain.min_unscaled + 1
        return (unscaled - domain.min_unscaled) % width + domain.min_unscaled
    raise AssertionError("reference overflow: %d" % unscaled)


def to_fraction(value):
    return Fraction(value.unscaled, 10 ** value.scale)


def random_fixed(rng, max_scale=8, digits=9):
    scale = rng.randint(0, max_scale)
    unscaled = rng.randint(-(10 ** digits), 10 ** digits)
    return Fixed(unscaled, scale)


class TestAgainstFraction(unittest.TestCase):

    def test_random_mul_div_pairs(self):
        rng = random.Random(20260922)
        domains = [
            Domain(bits=64, scale=6, rounding=mode, overflow=policy)
            for mode in MODES
            for policy in ("saturate", "wrap")
        ]
        for domain in domains:
            for _ in range(400):
                a = random_fixed(rng)
                b = random_fixed(rng)
                out_scale = rng.randint(0, 8)

                got = domain.mul(a, b, out_scale)
                want = ref_round_to_int(
                    to_fraction(a) * to_fraction(b) * 10 ** out_scale,
                    domain.rounding)
                self.assertEqual(got.scale, out_scale)
                self.assertEqual(got.unscaled, ref_fit(want, domain),
                                 (domain.rounding, domain.overflow, a, b))

                if b.unscaled == 0:
                    continue
                got = domain.div(a, b, out_scale)
                want = ref_round_to_int(
                    to_fraction(a) / to_fraction(b) * 10 ** out_scale,
                    domain.rounding)
                self.assertEqual(got.scale, out_scale)
                self.assertEqual(got.unscaled, ref_fit(want, domain),
                                 (domain.rounding, domain.overflow, a, b))

    def test_random_operation_sequences(self):
        rng = random.Random(77031)
        for mode in MODES:
            domain = Domain(bits=64, scale=6, rounding=mode, overflow="saturate")
            for _ in range(60):
                value = random_fixed(rng, max_scale=6)
                ref = to_fraction(value)
                for _ in range(25):
                    operand = random_fixed(rng, max_scale=6, digits=6)
                    out_scale = rng.randint(0, 6)
                    if rng.random() < 0.5 or operand.unscaled == 0:
                        value = domain.mul(value, operand, out_scale)
                        ref = to_fraction(operand) * ref
                    else:
                        value = domain.div(value, operand, out_scale)
                        ref = ref / to_fraction(operand)
                    want = ref_round_to_int(ref * 10 ** out_scale, mode)
                    want = ref_fit(want, domain)
                    self.assertEqual(value.unscaled, want, (mode, operand))
                    ref = Fraction(value.unscaled, 10 ** out_scale)

    def test_parse_matches_fraction_reference(self):
        rng = random.Random(4451)
        for mode in MODES:
            domain = Domain(bits=64, scale=4, rounding=mode, overflow="saturate")
            for _ in range(300):
                head = rng.randint(0, 10 ** 6)
                tail = "".join(rng.choice("0123456789")
                               for _ in range(rng.randint(1, 12)))
                sign = rng.choice(["", "-"])
                text = "%s%d.%s" % (sign, head, tail)
                got = domain.parse(text)
                exact = Fraction(head, 1) + Fraction(int(tail), 10 ** len(tail))
                if sign:
                    exact = -exact
                want = ref_fit(
                    ref_round_to_int(exact * 10 ** 4, mode), domain)
                self.assertEqual(got.unscaled, want, (mode, text))


class TestBoundaries(unittest.TestCase):

    def test_exact_half_at_every_sign(self):
        d = Domain(bits=64, scale=0, rounding="half_even")
        for num, want in ((5, 0), (15, 2), (25, 2), (35, 4),
                          (-5, 0), (-15, -2), (-25, -2), (-35, -4)):
            got = d.div(Fixed(num, 1), Fixed(1, 0), out_scale=0)
            self.assertEqual(got, Fixed(want, 0), num)

    def test_zero_operands_all_modes(self):
        for mode in MODES:
            d = Domain(bits=16, scale=2, rounding=mode)
            self.assertEqual(d.mul(Fixed(0, 2), Fixed(999, 2)), Fixed(0, 2))
            self.assertEqual(d.div(Fixed(0, 2), Fixed(999, 2)), Fixed(0, 2))
            self.assertEqual(d.parse("0.000"), Fixed(0, 2))
            self.assertEqual(d.text(Fixed(0, 2)), "0")

    def test_domain_edges_mul_div(self):
        d = Domain(bits=64, scale=6)
        top = Fixed(2 ** 63 - 1, 6)
        bottom = Fixed(-(2 ** 63), 6)
        self.assertEqual(d.mul(top, Fixed(1, 0)), top)
        self.assertEqual(d.mul(bottom, Fixed(1, 0)), bottom)
        self.assertEqual(d.div(top, Fixed(1, 0)), top)
        self.assertEqual(d.div(bottom, Fixed(1, 0)), bottom)
        sat = Domain(bits=64, scale=6, overflow="saturate")
        self.assertEqual(sat.mul(top, Fixed(2, 0)), top)
        self.assertEqual(sat.mul(bottom, Fixed(2, 0)), bottom)
        self.assertEqual(sat.div(bottom, Fixed(-1, 0)), top)

    def test_tiny_domain_all_policies(self):
        for policy, want in (("saturate", 1), ("wrap", -2)):
            d = Domain(bits=2, scale=0, overflow=policy)
            self.assertEqual(d.mul(Fixed(3, 0), Fixed(2, 0)), Fixed(want, 0))

    def test_text_round_trip_at_limits(self):
        d = Domain(bits=64, scale=6)
        for unscaled in (2 ** 63 - 1, -(2 ** 63), 0, 1, -1):
            value = Fixed(unscaled, 6)
            self.assertEqual(d.parse(d.text(value)), value)


class TestPerformance(unittest.TestCase):

    def test_million_mul_div_within_15_seconds(self):
        domain = Domain(bits=64, scale=6, rounding="half_even")
        rng = random.Random(20260922)
        operands = [Fixed(rng.randint(-10 ** 12, 10 ** 12) or 1, 6)
                    for _ in range(2048)]
        count = len(operands)
        start = time.monotonic()
        acc = 0
        for index in range(500_000):
            a = operands[index % count]
            b = operands[(index * 7 + 1) % count]
            acc += domain.mul(a, b, 6).unscaled
            acc += domain.div(a, b, 6).unscaled
        elapsed = time.monotonic() - start
        self.assertNotEqual(acc, 0)
        self.assertLess(elapsed, 15,
                        "1M mul/div took %.2fs" % elapsed)


if __name__ == "__main__":
    unittest.main()
