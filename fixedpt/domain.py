"""账目域：精度、域宽与运算入口。

Domain 是清算流程的操作入口：加减乘除都从它走。域宽管的是
定标整数的位数，64 位对应 -2**63 到 2**63-1，钱一旦越出
这个范围就不该再往账上记。
"""

import re

from fixedpt.errors import DomainOverflow, FixedPointError, ParseError
from fixedpt.number import Fixed
from fixedpt.rounding import (
    MODES,
    TRUNC,
    div_round,
    rescale,
)

_NUMBER_RE = re.compile(
    r"([+-]?)(\d+)?(?:\.(\d*))?(?:[eE]([+-]?\d+))?\Z")


class Domain:
    """账目域。

    bits: 定标整数的位宽，默认 64。
    scale: 账目精度，默认 6，即钱到微。
    overflow: 越界策略，默认 "raise"，越界抛 DomainOverflow。
    rounding: 乘除降精度时的舍入模式，默认 "trunc"（朝零截断）。

    overflow 还认 "wrap"（按二进制补码回绕）与 "saturate"（夹到
    域边界）。默认 "raise" 是安全档，越界绝不会悄悄绕过去。
    """

    def __init__(self, bits=64, scale=6, overflow="raise", rounding=TRUNC):
        if isinstance(bits, bool) or not isinstance(bits, int) or bits < 2:
            raise FixedPointError("bits must be an int >= 2: %r" % (bits,))
        if isinstance(scale, bool) or not isinstance(scale, int) or scale < 0:
            raise FixedPointError("scale must be a non-negative int: %r" % (scale,))
        if overflow not in ("raise", "wrap", "saturate"):
            raise FixedPointError("unsupported overflow policy: %r" % (overflow,))
        if rounding not in MODES:
            raise FixedPointError("unsupported rounding mode: %r" % (rounding,))
        self._bits = bits
        self._scale = scale
        self._overflow = overflow
        self._rounding = rounding
        self._limit = 1 << (bits - 1)

    # ---- 配置 ----

    @property
    def bits(self):
        return self._bits

    @property
    def scale(self):
        return self._scale

    @property
    def overflow(self):
        return self._overflow

    @property
    def rounding(self):
        return self._rounding

    @property
    def min_unscaled(self):
        return -self._limit

    @property
    def max_unscaled(self):
        return self._limit - 1

    # ---- 收口 ----

    def fit(self, unscaled):
        """把定标整数收进域内，按 overflow 策略处理。"""
        lo, hi = -self._limit, self._limit - 1
        if lo <= unscaled <= hi:
            return unscaled
        if self._overflow == "saturate":
            return hi if unscaled > hi else lo
        if self._overflow == "wrap":
            width = self._limit << 1
            got = unscaled % width
            if got >= self._limit:
                got -= width
            return got
        raise DomainOverflow(
            "unscaled out of domain: %d not in [%d, %d]" % (unscaled, lo, hi))

    def fixed(self, unscaled, scale=None):
        """造一个域内的定标值，scale 默认取域精度。"""
        return Fixed(self.fit(unscaled), self._scale if scale is None else scale)

    # ---- 运算 ----

    @staticmethod
    def _pair(a, b):
        if not isinstance(a, Fixed) or not isinstance(b, Fixed):
            raise FixedPointError("expected Fixed on both sides: %r, %r" % (a, b))
        return a, b

    def _mode(self, rounding):
        mode = self._rounding if rounding is None else rounding
        if mode not in MODES:
            raise FixedPointError("unsupported rounding mode: %r" % (mode,))
        return mode

    def add(self, a, b):
        """加，结果收口。"""
        got = a + b
        return Fixed(self.fit(got.unscaled), got.scale)

    def sub(self, a, b):
        """减，结果收口。"""
        got = a - b
        return Fixed(self.fit(got.unscaled), got.scale)

    def mul(self, a, b, out_scale=None, rounding=None):
        """乘：乘积先定标到 out_scale，再按域收口。

        精确乘积的 scale 是两边 scale 之和，先按舍入模式落到 out_scale
        （默认取两边较大的 scale），再过 fit。舍入先于收口，收口的
        越界处理由 overflow 决定。
        """
        a, b = self._pair(a, b)
        if out_scale is None:
            out_scale = max(a.scale, b.scale)
        if isinstance(out_scale, bool) or not isinstance(out_scale, int) \
                or out_scale < 0:
            raise FixedPointError(
                "out_scale must be a non-negative int: %r" % (out_scale,))
        mode = self._mode(rounding)
        exact_scale = a.scale + b.scale
        unscaled = a.unscaled * b.unscaled
        if out_scale > exact_scale:
            unscaled *= 10 ** (out_scale - exact_scale)
        elif out_scale < exact_scale:
            unscaled = rescale(unscaled, 10 ** (exact_scale - out_scale), mode)
        return Fixed(self.fit(unscaled), out_scale)

    def div(self, a, b, out_scale=None, rounding=None):
        """除：商先按舍入模式落到 out_scale，再按域收口。

        out_scale 默认取两边较大的 scale；除数为零抛 ZeroDivisionError。
        """
        a, b = self._pair(a, b)
        if b.unscaled == 0:
            raise ZeroDivisionError("division by zero")
        if out_scale is None:
            out_scale = max(a.scale, b.scale)
        if isinstance(out_scale, bool) or not isinstance(out_scale, int) \
                or out_scale < 0:
            raise FixedPointError(
                "out_scale must be a non-negative int: %r" % (out_scale,))
        mode = self._mode(rounding)
        shift = b.scale + out_scale - a.scale
        if shift >= 0:
            unscaled = div_round(a.unscaled * 10 ** shift, b.unscaled, mode)
        else:
            unscaled = div_round(a.unscaled, b.unscaled * 10 ** (-shift), mode)
        return Fixed(self.fit(unscaled), out_scale)

    # ---- 文本互转 ----

    def parse(self, text, rounding=None):
        """文本转域精度的 Fixed。

        认普通小数和科学计数法（大小写 E 均可），正负号、多余的前导
        零与末尾零都认。超出域精度的小数按模式舍入，再过 fit 收口；
        无法辨认的文本抛 ParseError。
        """
        if not isinstance(text, str):
            raise ParseError("expected a decimal string, got %r" % (text,))
        match = _NUMBER_RE.match(text)
        if match is None:
            raise ParseError("not a decimal number: %r" % (text,))
        sign, whole, frac, exp_text = match.groups()
        digits = (whole or "") + (frac or "")
        if not digits:
            raise ParseError("not a decimal number: %r" % (text,))
        exponent = int(exp_text) if exp_text is not None else 0
        exponent -= len(frac or "")
        unscaled = int(digits)
        if sign == "-":
            unscaled = -unscaled
        target = self._scale
        shift = exponent + target
        if shift >= 0:
            unscaled *= 10 ** shift
        else:
            unscaled = rescale(unscaled, 10 ** (-shift), self._mode(rounding))
        return Fixed(self.fit(unscaled), target)

    def text(self, value):
        """域精度的 Fixed 转规范文本：普通小数、去多余零、来回稳定。

        负零归成零；整数不带小数点。
        """
        if not isinstance(value, Fixed):
            raise FixedPointError("expected Fixed, got %r" % (value,))
        unscaled, scale = value.unscaled, value.scale
        if unscaled == 0:
            return "0"
        negative = unscaled < 0
        digits = str(-unscaled if negative else unscaled)
        if scale == 0:
            body = digits
        else:
            frac_digits = digits[-scale:] if len(digits) > scale else \
                "0" * (scale - len(digits)) + digits
            int_digits = digits[:-scale] if len(digits) > scale else "0"
            frac_digits = frac_digits.rstrip("0")
            body = int_digits + ("." + frac_digits if frac_digits else "")
        return ("-" + body) if negative else body
