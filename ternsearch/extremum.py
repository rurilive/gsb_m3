"""ternsearch 的朴素极值实现（改造前的现状）。

现在只有一条路径：把定义域里的每个整数点、或离散序列里的每个下标逐个
取出，算一遍函数值，边扫边记最优，扫完就得到最小值、最大值、峰值与位置。
线性枚举，定义域一大就慢；没有收窄定义域的任何加速结构。

三分法收窄、导数或差分加二分、斐波那契搜索或黄金分割比、单峰判定与
求值次数对照见任务描述。
"""


class ExtremumError(ValueError):
    """极值工具的错误基类，非法区间与非法类型都从这里抛出。"""


class UnimodalError(ExtremumError):
    """单峰或凸性前提被违反时抛出。"""


def _as_int(name, value):
    """把参数收成整数，布尔另有分支，其余非整数直接报错。"""
    if isinstance(value, bool):
        raise ExtremumError("%s must be an int, got bool" % name)
    if not isinstance(value, int):
        raise ExtremumError("%s must be an int, got %r" % (name, value))
    return value


def bisect_left_ge(sequence, target):
    """在非降序列里找第一个大于等于 target 的下标；全都小于就返回长度。"""
    lo = 0
    hi = len(sequence)
    while lo < hi:
        mid = (lo + hi) // 2
        if sequence[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def convex_vertex_coeffs(a, b, c):
    """把二次函数的三个系数取出，检查二次项不为零，返回整数化的三元组。"""
    for name, value in (("a", a), ("b", b), ("c", c)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ExtremumError("coeff %s must be a number, got %r" % (name, value))
    if a == 0:
        raise ExtremumError("quadratic coefficient must not be zero")
    return a, b, c


class EnumCounter:
    """记录一次求解里求值函数被调用了多少次，供规模对照使用。"""

    def __init__(self):
        self.calls = 0

    def reset(self):
        """把计数清零，重复求解时可复用同一个计数器。"""
        self.calls = 0
        return self

    def wrap(self, func):
        """把传入的函数包一层，每次调用自增计数后返回原结果。"""
        if not callable(func):
            raise ExtremumError("func must be callable")
        counter = self

        def counted(x):
            counter.calls += 1
            return func(x)

        return counted


class DiscreteSequence:
    """一串离散数据，视作按位置排列的单峰序列，只能用下标取数。"""

    def __init__(self, values):
        vals = []
        for item in values:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ExtremumError("sequence value must be a number, got %r" % (item,))
            vals.append(item)
        if not vals:
            raise ExtremumError("sequence must not be empty")
        self._values = tuple(vals)

    def __len__(self):
        return len(self._values)

    def value_at(self, index):
        """按下标取值，越界抛索引错误。"""
        if index < 0 or index >= len(self._values):
            raise ExtremumError("index out of range: %r" % (index,))
        return self._values[index]

    def values(self):
        """返回整串数据的副本。"""
        return self._values

    def is_unimodal(self):
        """逐位置扫一遍，判断是否存在峰值使左侧不降、右侧不升。"""
        n = len(self._values)
        if n == 1:
            return True
        first_down = -1
        for i in range(n - 1):
            if self._values[i + 1] < self._values[i]:
                first_down = i
                break
        if first_down == -1:
            return True
        for i in range(first_down, n - 1):
            if self._values[i + 1] > self._values[i]:
                return False
        return True

    def peak_index(self):
        """逐位置枚举，返回峰值下标；并列时取最左那个。非单峰抛错。"""
        if not self.is_unimodal():
            raise UnimodalError("sequence is not unimodal")
        n = len(self._values)
        best = 0
        for i in range(1, n):
            if self._values[i] > self._values[best]:
                best = i
        return best


class PeakFinder:
    """在一元函数上求极值，全部靠枚举定义域实现。

    定义域用闭区间 [lo, hi] 描述，元素是整数；求最小值、最大值、
    峰值位置、凸函数最值、离散序列峰值，走的都是同一套逐点枚举。
    """

    def __init__(self):
        self._counter = EnumCounter()

    def counter(self):
        """返回本次求解共用的求值计数器。"""
        return self._counter

    def _check_range(self, lo, hi):
        """检查区间端点类型合法，返回整数化后的左右端点。"""
        lo = _as_int("lo", lo)
        hi = _as_int("hi", hi)
        return lo, hi

    def minimize(self, func, lo, hi, key=None):
        """枚举 [lo, hi] 每个整数点求最小值，返回 (位置, 值)。"""
        if not callable(func):
            raise ExtremumError("func must be callable")
        lo, hi = self._check_range(lo, hi)
        if lo > hi:
            raise ExtremumError("invalid range: lo=%d hi=%d" % (lo, hi))
        best_pos = None
        best_val = None
        for x in range(lo, hi + 1):
            value = func(x)
            self._counter.calls += 1
            if key is not None:
                value = key(value)
            if best_val is None or value < best_val:
                best_val = value
                best_pos = x
        return best_pos, func(best_pos)

    def maximize(self, func, lo, hi, key=None):
        """枚举 [lo, hi] 每个整数点求最大值，返回 (位置, 值)。"""
        if not callable(func):
            raise ExtremumError("func must be callable")
        lo, hi = self._check_range(lo, hi)
        if lo > hi:
            raise ExtremumError("invalid range: lo=%d hi=%d" % (lo, hi))
        best_pos = None
        best_val = None
        for x in range(lo, hi + 1):
            value = func(x)
            self._counter.calls += 1
            if key is not None:
                value = key(value)
            if best_val is None or value > best_val:
                best_val = value
                best_pos = x
        return best_pos, func(best_pos)

    def peak_position(self, func, lo, hi, key=None):
        """枚举 [lo, hi] 求峰值位置，取函数值最大的下标；并列取最左。"""
        return self.maximize(func, lo, hi, key=key)[0]

    def convex_minimum(self, a, b, c, lo, hi):
        """枚举二次函数在 [lo, hi] 上的最小值，返回 (位置, 值)。"""
        a, b, c = convex_vertex_coeffs(a, b, c)
        if a < 0:
            raise UnimodalError("quadratic is not convex: a=%r" % (a,))
        lo, hi = self._check_range(lo, hi)
        if lo > hi:
            raise ExtremumError("invalid range: lo=%d hi=%d" % (lo, hi))
        best_pos = lo
        best_val = a * lo * lo + b * lo + c
        for x in range(lo + 1, hi + 1):
            value = a * x * x + b * x + c
            self._counter.calls += 1
            if value < best_val:
                best_val = value
                best_pos = x
        return best_pos, best_val

    def integer_maximum(self, func, lo, hi, key=None):
        """枚举整数定义域上的最大值，是 maximize 的另一个入口名。"""
        return self.maximize(func, lo, hi, key=key)

    def sequence_peak(self, sequence):
        """把离散数据视作单峰序列，逐下标枚举求峰值位置。"""
        if not isinstance(sequence, DiscreteSequence):
            sequence = DiscreteSequence(sequence)
        return sequence.peak_index()

    def eval_count(self, func, lo, hi):
        """跑一遍枚举求最小值，返回这次枚举的求值次数。"""
        self._counter.reset()
        self.minimize(func, lo, hi)
        return self._counter.calls
