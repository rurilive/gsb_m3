"""账目域：精度、域宽与运算入口。

Domain 是清算流程的操作入口：加减乘除都从它走。域宽管的是
定标整数的位数，64 位对应 -2**63 到 2**63-1，钱一旦越出
这个范围就不该再往账上记。
"""

import re

from fixedpt.errors import DomainOverflow, FixedPointError, ParseError
from fixedpt.number import Fixed
from fixedpt.rounding import MODES, check_mode

OVERFLOW_POLICIES = ("raise", "saturate", "wrap")

# 科学计数法的指数上限，防止 1e999999999 这类文本撑出天文数字。
_MAX_EXPONENT = 100_000

_TEXT_PATTERN = re.compile(
    r"^\s*(?P<sign>[+-]?)"
    r"(?:(?P<head>\d+)(?:\.(?P<tail>\d*))?|\.(?P<tail_only>\d+))"
    r"(?:[eE](?P<exp>[+-]?\d+))?\s*$")


class Domain:
    """账目域。

    bits: 定标整数的位宽，默认 64。
    scale: 账目精度，默认 6，即钱到微。
    overflow: 越界策略，默认 "raise"，越界抛 DomainOverflow；
        "saturate" 饱和到域边界，"wrap" 按位宽回绕。
    rounding: 乘除落定标与文本解析的舍入模式，默认 "truncate"
        朝零截断；可选值见 fixedpt.rounding.MODES。
    """

    def __init__(self, bits=64, scale=6, overflow="raise", rounding="truncate"):
        if isinstance(bits, bool) or not isinstance(bits, int) or bits < 2:
            raise FixedPointError("bits must be an int >= 2: %r" % (bits,))
        if isinstance(scale, bool) or not isinstance(scale, int) or scale < 0:
            raise FixedPointError("scale must be a non-negative int: %r" % (scale,))
        if overflow not in OVERFLOW_POLICIES:
            raise FixedPointError("unsupported overflow policy: %r" % (overflow,))
        self._bits = bits
        self._scale = scale
        self._overflow = overflow
        self._rounding = check_mode(rounding)
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
        """把定标整数收进域内，按 overflow 策略处理。

        raise 抛 DomainOverflow；saturate 饱和到最近的边界；
        wrap 按位宽做二进制补码回绕。
        """
        if -self._limit <= unscaled <= self._limit - 1:
            return unscaled
        if self._overflow == "raise":
            raise DomainOverflow(
                "unscaled out of domain: %d not in [%d, %d]"
                % (unscaled, -self._limit, self._limit - 1))
        if self._overflow == "saturate":
            return self._limit - 1 if unscaled > 0 else -self._limit
        width = self._limit << 1
        return (unscaled + self._limit) % width - self._limit

    def _resolve_rounding(self, rounding):
        return self._rounding if rounding is None else check_mode(rounding)

    def fixed(self, unscaled, scale=None):
        """造一个域内的定标值，scale 默认取域精度。"""
        return Fixed(self.fit(unscaled), self._scale if scale is None else scale)

    # ---- 运算 ----

    def add(self, a, b):
        """加，结果收口。"""
        got = a + b
        return Fixed(self.fit(got.unscaled), got.scale)

    def sub(self, a, b):
        """减，结果收口。"""
        got = a - b
        return Fixed(self.fit(got.unscaled), got.scale)

    def mul(self, a, b, out_scale=None, rounding=None):
        """乘：乘积先按两边 scale 之和铺开，再落到 out_scale。

        out_scale 默认取两边较大的 scale，低位按 rounding 舍入，
        缺省用域的舍入模式。定标后按域的 overflow 策略收口。
        """
        got = a.mul(b, out_scale, self._resolve_rounding(rounding))
        return Fixed(self.fit(got.unscaled), got.scale)

    def div(self, a, b, out_scale=None, rounding=None):
        """除：商落到 out_scale，默认取两边较大的 scale。

        低位按 rounding 舍入，缺省用域的舍入模式；定标后按域的
        overflow 策略收口。除数为零抛 ZeroDivisionError。
        """
        got = a.div(b, out_scale, self._resolve_rounding(rounding))
        return Fixed(self.fit(got.unscaled), got.scale)

    # ---- 文本互转 ----

    def parse(self, text, scale=None, rounding=None):
        """把文本解析成域内的定标值，scale 默认取域精度。

        认普通小数、科学计数法（1.2e3、5E-2）、前导与末尾多余的零、
        首尾空白与正负号。小数位超出目标精度时按 rounding 舍入，
        缺省用域的舍入模式；结果按域的 overflow 策略收口。
        文本不合法抛 ParseError，指数超过正负 _MAX_EXPONENT 也算不合法。
        """
        if not isinstance(text, str):
            raise ParseError("expected text to parse: %r" % (text,))
        match = _TEXT_PATTERN.match(text)
        if match is None:
            raise ParseError("cannot parse fixed-point text: %r" % (text,))
        if scale is None:
            scale = self._scale
        elif isinstance(scale, bool) or not isinstance(scale, int) or scale < 0:
            raise FixedPointError("scale must be a non-negative int: %r" % (scale,))
        rounding = self._resolve_rounding(rounding)
        head = match.group("head") or ""
        tail = match.group("tail")
        if tail is None:
            tail = match.group("tail_only") or ""
        exp_text = match.group("exp")
        exponent = int(exp_text) if exp_text else 0
        if abs(exponent) > _MAX_EXPONENT:
            raise ParseError("exponent out of range: %r" % (text,))
        digits = (head + tail).lstrip("0") or "0"
        try:
            unscaled = int(digits)
        except ValueError:
            raise ParseError("too many digits: %r" % (text,))
        if match.group("sign") == "-":
            unscaled = -unscaled
        value_scale = len(tail) - exponent
        if value_scale < 0:
            unscaled *= 10 ** (-value_scale)
            value_scale = 0
        got = Fixed(unscaled, value_scale).rescaled(scale, rounding)
        return Fixed(self.fit(got.unscaled), scale)

    def text(self, value):
        """把定标值格式化成文本，末尾多余的零去掉。

        输出是普通十进制写法，不带科学计数法；parse 能原样读回，
        域精度下的值来回倒稳定。
        """
        if not isinstance(value, Fixed):
            raise FixedPointError("expected Fixed: %r" % (value,))
        unscaled = value.unscaled
        sign = "-" if unscaled < 0 else ""
        digits = str(abs(unscaled))
        if value.scale == 0:
            return sign + digits
        digits = digits.rjust(value.scale + 1, "0")
        head = digits[:-value.scale]
        tail = digits[-value.scale:].rstrip("0")
        if not tail:
            return sign + head
        return "%s%s.%s" % (sign, head, tail)
