"""账目域：精度、域宽与运算入口。

Domain 是清算流程的操作入口：加减乘除都从它走。域宽管的是
定标整数的位数，64 位对应 -2**63 到 2**63-1，钱一旦越出
这个范围就不该再往账上记。
"""

from fixedpt.errors import DomainOverflow, FixedPointError
from fixedpt.number import Fixed


class Domain:
    """账目域。

    bits: 定标整数的位宽，默认 64。
    scale: 账目精度，默认 6，即钱到微。
    overflow: 越界策略，默认 "raise"，越界抛 DomainOverflow。
    """

    def __init__(self, bits=64, scale=6, overflow="raise"):
        if isinstance(bits, bool) or not isinstance(bits, int) or bits < 2:
            raise FixedPointError("bits must be an int >= 2: %r" % (bits,))
        if isinstance(scale, bool) or not isinstance(scale, int) or scale < 0:
            raise FixedPointError("scale must be a non-negative int: %r" % (scale,))
        if overflow not in ("raise",):
            raise FixedPointError("unsupported overflow policy: %r" % (overflow,))
        self._bits = bits
        self._scale = scale
        self._overflow = overflow
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
    def min_unscaled(self):
        return -self._limit

    @property
    def max_unscaled(self):
        return self._limit - 1

    # ---- 收口 ----

    def fit(self, unscaled):
        """把定标整数收进域内，按 overflow 策略处理。"""
        if -self._limit <= unscaled <= self._limit - 1:
            return unscaled
        raise DomainOverflow(
            "unscaled out of domain: %d not in [%d, %d]"
            % (unscaled, -self._limit, self._limit - 1))

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

    def mul(self, a, b, out_scale=None):
        """乘：乘积先按两边 scale 之和铺开，再落到 out_scale。

        out_scale 默认取两边较大的 scale，低位朝零截断。
        结果不收口，越界值原样留在结果里。
        """
        return a.mul(b, out_scale)

    def div(self, a, b, out_scale=None):
        """除：商落到 out_scale，默认取两边较大的 scale，低位朝零截断。

        结果不收口。
        """
        return a.div(b, out_scale)
