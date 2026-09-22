"""定标小数值。

小数按 10 的幂缩放成整数存放：unscaled 是那个整数，scale 是
小数点后的位数，值是 unscaled / 10 ** scale。比如 12.05 在
scale=2 下是 Fixed(1205, 2)。

Fixed 只做精确运算与比较，不带精度策略，也不做范围检查；
精度、舍入与域宽在 Domain 那头管。
"""

from fixedpt.errors import FixedPointError
from fixedpt.rounding import check_mode, div_round


class Fixed:
    """不可变的定标小数。

    scale 是非负整数；unscaled 是任意整数。构造与运算都不做
    范围检查，范围与舍入策略在外面的 Domain。
    """

    __slots__ = ("_unscaled", "_scale")

    def __init__(self, unscaled, scale=0):
        if isinstance(unscaled, bool) or not isinstance(unscaled, int):
            raise FixedPointError("unscaled must be int: %r" % (unscaled,))
        if isinstance(scale, bool) or not isinstance(scale, int) or scale < 0:
            raise FixedPointError("scale must be a non-negative int: %r" % (scale,))
        self._unscaled = unscaled
        self._scale = scale

    # ---- 读数 ----

    @property
    def unscaled(self):
        """缩放后的整数。"""
        return self._unscaled

    @property
    def scale(self):
        """小数点后的位数。"""
        return self._scale

    def is_zero(self):
        return self._unscaled == 0

    def sign(self):
        """负返回 -1，零返回 0，正返回 1。"""
        if self._unscaled > 0:
            return 1
        if self._unscaled < 0:
            return -1
        return 0

    def __bool__(self):
        return self._unscaled != 0

    # ---- 对齐 ----

    @staticmethod
    def _pair(a, b):
        if not isinstance(a, Fixed) or not isinstance(b, Fixed):
            raise FixedPointError("expected Fixed on both sides: %r, %r" % (a, b))
        return a, b

    def _aligned(self, other):
        """两边抬到共同的 scale，取大的那个。

        往大 scale 走是乘 10 的幂，精确无误差。
        返回 (自身的整数, 对方的整数, 共同 scale)。
        """
        a, b = self._pair(self, other)
        if a._scale == b._scale:
            return a._unscaled, b._unscaled, a._scale
        if a._scale > b._scale:
            return a._unscaled, b._unscaled * 10 ** (a._scale - b._scale), a._scale
        return a._unscaled * 10 ** (b._scale - a._scale), b._unscaled, b._scale

    # ---- 加减、取反、绝对值 ----

    def __add__(self, other):
        su, ou, scale = self._aligned(other)
        return Fixed(su + ou, scale)

    def __sub__(self, other):
        su, ou, scale = self._aligned(other)
        return Fixed(su - ou, scale)

    def __neg__(self):
        return Fixed(-self._unscaled, self._scale)

    def __abs__(self):
        return Fixed(abs(self._unscaled), self._scale)

    # ---- 比较 ----

    def __eq__(self, other):
        if not isinstance(other, Fixed):
            return NotImplemented
        su, ou, _ = self._aligned(other)
        return su == ou

    def __lt__(self, other):
        su, ou, _ = self._aligned(other)
        return su < ou

    def __le__(self, other):
        su, ou, _ = self._aligned(other)
        return su <= ou

    def __gt__(self, other):
        su, ou, _ = self._aligned(other)
        return su > ou

    def __ge__(self, other):
        su, ou, _ = self._aligned(other)
        return su >= ou

    def __hash__(self):
        """跨 scale 相等则同 hash，按值规约后再散列。"""
        u, s = self._unscaled, self._scale
        while s > 0 and u % 10 == 0:
            u //= 10
            s -= 1
        return hash((u, s))

    # ---- 定标与乘除 ----

    def rescaled(self, scale, rounding="truncate"):
        """落到指定 scale。

        往大走精确；往小走丢掉低位，低位按 rounding 模式舍入，
        默认朝零截断。
        """
        if isinstance(scale, bool) or not isinstance(scale, int) or scale < 0:
            raise FixedPointError("scale must be a non-negative int: %r" % (scale,))
        check_mode(rounding)
        if scale >= self._scale:
            return Fixed(self._unscaled * 10 ** (scale - self._scale), scale)
        return Fixed(
            div_round(self._unscaled, 10 ** (self._scale - scale), rounding), scale)

    def mul(self, other, out_scale=None, rounding="truncate"):
        """乘：两边 scale 之和是精确乘积，再落到 out_scale。

        out_scale 默认取两边较大的 scale。落定标时低位按 rounding
        模式舍入，默认朝零截断。
        结果不收口。
        """
        a, b = self._pair(self, other)
        if out_scale is None:
            out_scale = max(a._scale, b._scale)
        exact = Fixed(a._unscaled * b._unscaled, a._scale + b._scale)
        return exact.rescaled(out_scale, rounding)

    def div(self, other, out_scale=None, rounding="truncate"):
        """除：商落到 out_scale，默认取两边较大的 scale。

        低位按 rounding 模式舍入，默认朝零截断，结果不收口；
        除数为零抛 ZeroDivisionError。
        """
        a, b = self._pair(self, other)
        if b._unscaled == 0:
            raise ZeroDivisionError("division by zero")
        if out_scale is None:
            out_scale = max(a._scale, b._scale)
        check_mode(rounding)
        shift = b._scale + out_scale - a._scale
        if shift >= 0:
            got = div_round(a._unscaled * 10 ** shift, b._unscaled, rounding)
        else:
            got = div_round(a._unscaled, b._unscaled * 10 ** (-shift), rounding)
        return Fixed(got, out_scale)

    def __mul__(self, other):
        return self.mul(other)

    def __truediv__(self, other):
        return self.div(other)

    def __repr__(self):
        return "Fixed(unscaled=%d, scale=%d)" % (self._unscaled, self._scale)
