"""拿 fractions.Fraction 当独立参考，随机小数与随机运算序列逐一对拍。

覆盖五种舍入模式、正负号、跨 scale、科学计数法文本解析，以及
Fixed 层乘除与 Domain 层 trunc 默认口径的一致性。
"""

import random
import unittest
from fractions import Fraction

from fixedpt import CEIL, FLOOR, HALF_EVEN, TRUNC, UP, Domain, Fixed

MODES = (TRUNC, HALF_EVEN, UP, FLOOR, CEIL)


def ref_round(value, mode):
    """Fraction 舍入到整数，五种模式的独立参考实现。"""
    assert isinstance(value, Fraction)
    if value.denominator == 1:
        return value.numerator // value.denominator
    floor = value.numerator // value.denominator
    if mode == FLOOR:
        return floor
    if mode == CEIL:
        return floor + 1
    if mode == TRUNC:
        return floor if value >= 0 else floor + 1
    if mode == UP:
        return floor + 1 if value >= 0 else floor
    if mode == HALF_EVEN:
        frac = value - floor
        half = Fraction(1, 2)
        if frac < half:
            return floor
        if frac > half:
            return floor + 1
        return floor if floor % 2 == 0 else floor + 1
    raise AssertionError(mode)


def ref_mul(a, b, out_scale, mode):
    value = Fraction(a.unscaled * b.unscaled,
                     10 ** (a.scale + b.scale))
    return ref_round(value * 10 ** out_scale, mode)


def ref_div(a, b, out_scale, mode):
    shift = b.scale + out_scale - a.scale
    if shift >= 0:
        value = Fraction(a.unscaled * 10 ** shift, b.unscaled)
    else:
        value = Fraction(a.unscaled, b.unscaled * 10 ** (-shift))
    return ref_round(value, mode)


def ref_parse(text, scale, mode):
    """不走 float，把十进制文本（含科学计数法）拆成 Fraction。"""
    lower = text.lower()
    if "e" in lower:
        mantissa, exp_text = text[:lower.index("e")], text[lower.index("e") + 1:]
    else:
        mantissa, exp_text = text, ""
    sign = 1
    if mantissa[:1] in "+-":
        if mantissa[0] == "-":
            sign = -1
        mantissa = mantissa[1:]
    whole, _, frac = mantissa.partition(".")
    digits = (whole or "") + (frac or "")
    value = Fraction(int(sign), 1) * Fraction(
        int(digits or "0"), 10 ** len(frac or ""))
    if exp_text:
        exponent = int(exp_text)
        if exponent >= 0:
            value = value * Fraction(10 ** exponent, 1)
        else:
            value = value * Fraction(1, 10 ** (-exponent))
    value = value * Fraction(10 ** scale, 1)
    assert isinstance(value, Fraction)
    return ref_round(value, mode)


class TestRandomFixedAgainstFraction(unittest.TestCase):

    def setUp(self):
        self.rand = random.Random(20260922)
        # 256 位的宽域，让随机对拍不被收口干扰
        self.d = Domain(bits=256, scale=6, rounding=HALF_EVEN)

    def random_fixed(self):
        scale = self.rand.randrange(0, 8)
        magnitude = 10 ** self.rand.randrange(0, 12)
        unscaled = self.rand.randrange(-magnitude, magnitude + 1) if magnitude \
            else 0
        return Fixed(unscaled, scale)

    def test_mul_matches_fraction_all_modes(self):
        for _ in range(4000):
            a, b = self.random_fixed(), self.random_fixed()
            out_scale = self.rand.randrange(0, 8)
            mode = self.rand.choice(MODES)
            got = self.d.mul(a, b, out_scale=out_scale, rounding=mode)
            want = ref_mul(a, b, out_scale, mode)
            self.assertEqual(got, Fixed(want, out_scale),
                             (a, b, out_scale, mode))

    def test_div_matches_fraction_all_modes(self):
        for _ in range(4000):
            a = self.random_fixed()
            b = self.random_fixed()
            if b.is_zero():
                b = Fixed(1, b.scale)
            out_scale = self.rand.randrange(0, 8)
            mode = self.rand.choice(MODES)
            got = self.d.div(a, b, out_scale=out_scale, rounding=mode)
            want = ref_div(a, b, out_scale, mode)
            self.assertEqual(got, Fixed(want, out_scale),
                             (a, b, out_scale, mode))

    def test_negative_values_covered(self):
        """强制负被除数与负除数各方向的舍入都和 Fraction 对上。"""
        d = Domain(bits=256, scale=3)
        for na in range(-200, 201):
            for nb in (-7, -3, -2, 2, 3, 7):
                a, b = Fixed(na, 1), Fixed(nb, 0)
                for mode in MODES:
                    self.assertEqual(
                        d.div(a, b, out_scale=2, rounding=mode),
                        Fixed(ref_div(a, b, 2, mode), 2),
                        (a, b, mode))

    def test_fixed_layer_trunc_matches_fraction(self):
        """Fixed.mul/div/rescaled 的默认 trunc 口径与参考一致，正负都覆盖。"""
        for _ in range(3000):
            a, b = self.random_fixed(), self.random_fixed()
            if b.is_zero():
                b = Fixed(1, b.scale)
            out_scale = self.rand.randrange(0, 8)
            self.assertEqual(a.mul(b, out_scale),
                             Fixed(ref_mul(a, b, out_scale, TRUNC),
                                   out_scale))
            self.assertEqual(a.div(b, out_scale),
                             Fixed(ref_div(a, b, out_scale, TRUNC),
                                   out_scale))

    def test_random_operation_chains(self):
        """随机乘除序列，逐步对拍，结果继续当下一轮输入。"""
        start = self.rand.randrange(-10 ** 9, 10 ** 9)
        value = Fixed(start, 6)
        ref = Fraction(start, 10 ** 6)
        for _ in range(800):
            other = self.random_fixed()
            if other.is_zero():
                other = Fixed(1, other.scale)
            mode = self.rand.choice(MODES)
            out_scale = self.rand.randrange(0, 8)
            other_value = Fraction(other.unscaled, 10 ** other.scale)
            if self.rand.randrange(2):
                value = self.d.mul(value, other, out_scale=out_scale,
                                   rounding=mode)
                ref = ref_round(ref * other_value * 10 ** out_scale, mode)
            else:
                value = self.d.div(value, other, out_scale=out_scale,
                                   rounding=mode)
                ref = ref_round(
                    Fraction(ref, other_value) * 10 ** out_scale, mode)
            self.assertEqual(value, Fixed(ref, out_scale))
            ref = Fraction(ref, 10 ** out_scale)


class TestRandomTextAgainstFraction(unittest.TestCase):

    def setUp(self):
        self.rand = random.Random(424242)
        self.d = Domain(bits=256, scale=4, rounding=HALF_EVEN)

    def random_decimal_text(self):
        sign = self.rand.choice(["", "-", "+"])
        whole = "".join(self.rand.choice("000123456789")
                        for _ in range(self.rand.randrange(1, 5)))
        if self.rand.randrange(2):
            frac = "".join(self.rand.choice("0123456789")
                           for _ in range(self.rand.randrange(0, 7)))
            mantissa = whole + "." + frac
        else:
            mantissa = whole
        if self.rand.randrange(2):
            mantissa += self.rand.choice(["e", "E"]) + self.rand.choice(
                ["", "+", "-"]) + str(self.rand.randrange(0, 9))
        return sign + mantissa

    def test_parse_matches_fraction(self):
        for _ in range(5000):
            text = self.random_decimal_text()
            # 生成器偶会造出空指数（"1e+"），库拒绝、参考也没法读，跳过
            if text[-1:] in "+-eE":
                continue
            mode = self.rand.choice(MODES)
            got = self.d.parse(text, rounding=mode)
            want = ref_parse(text, 4, mode)
            self.assertEqual(got, Fixed(want, 4), (text, mode))

    def test_text_roundtrip_exhaustive_small(self):
        for unscaled in range(-20000, 20001):
            value = Fixed(unscaled, 4)
            self.assertEqual(self.d.parse(self.d.text(value)), value,
                             unscaled)


if __name__ == "__main__":
    unittest.main()
