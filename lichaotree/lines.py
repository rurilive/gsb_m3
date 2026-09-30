"""直线集合的朴素实现（改造前基线）。

内部只留一个直线列表，每条直线连同它的插入序号原样存下来。
每问一次某横坐标的最值，就把已插入的全部直线逐条求值再取最值；
每问一次区间的折线最小值，就把定义域内的整数横坐标逐个点名，
每个点再逐条求值。插入越多、查询越多，白算的次数就越多。

这里没有按定义域建的树、没有中点比较、没有区间合并，
也没有能共享计算的批量路径。结果是对的，只是规模一大就慢。
"""


class Erro(Exception):
    """本库全部异常的基类。"""


class IllegalArgument(Erro):
    """参数不合格，例如类型不对、定义域区间非法、上下界类型不对。"""


class Line:
    """一条直线 y = k x + b。

    只读地持有斜率 k、截距 b 与插入序号 ident。
    系数与取值都按普通整数处理，允许为负，不做任何取模。
    """

    __slots__ = ("_k", "_b", "_ident")

    def __init__(self, k, b, ident):
        for v in (k, b, ident):
            if isinstance(v, bool) or not isinstance(v, int):
                raise IllegalArgument("直线系数与序号必须是整数")
        self._k = int(k)
        self._b = int(b)
        self._ident = int(ident)

    @property
    def k(self):
        """斜率。"""
        return self._k

    @property
    def b(self):
        """截距。"""
        return self._b

    @property
    def ident(self):
        """插入序号，越小表示插入得越早。"""
        return self._ident

    def value_at(self, x):
        """在横坐标 x 处的取值，按普通整数相乘相加，可为负。"""
        return self._k * int(x) + self._b

    def __repr__(self):
        return "Line(k={}, b={}, ident={})".format(self._k, self._b, self._ident)


class NaiveLines:
    """朴素直线集合：插入即保存，查询即逐条求值。

    - 插入直线只做保存，不看任何已有直线，插入一律成功。
    - 单点最值把已插入的全部直线逐条求值再取最值。
    - 区间最小值把定义域内的整数横坐标逐个点名，每个点再逐条求值。
    - 并列取先：取值相同就取插入序号较小（插入较早）的那条。
    """

    def __init__(self, domain):
        if not isinstance(domain, (list, tuple)) or len(domain) != 2:
            raise IllegalArgument("定义域须是长度为二的列表或元组")
        lo, hi = domain
        lo = self._as_int(lo, "定义域下界")
        hi = self._as_int(hi, "定义域上界")
        if lo > hi:
            raise IllegalArgument("定义域下界不得大于上界")
        self._lo = lo
        self._hi = hi
        self._lines = []
        self._next_ident = 0

    # ---- 基本信息 ------------------------------------------------------

    def domain(self):
        """返回定义域二元组（下界，上界）。"""
        return (self._lo, self._hi)

    def __len__(self):
        """当前已插入的直线条数。"""
        return len(self._lines)

    def lines(self):
        """按插入先后返回全部直线的浅拷贝。"""
        return list(self._lines)

    # ---- 插入 ----------------------------------------------------------

    def add_line(self, k, b):
        """插入一条直线 y = k x + b，返回它的插入序号。

        朴素实现不理会已插入的直线，直接追加保存，必然成功。
        """
        line = Line(k, b, self._next_ident)
        self._next_ident += 1
        self._lines.append(line)
        return line.ident

    # ---- 查询（每次逐条求值） ------------------------------------------

    def query_min(self, x):
        """全部直线在横坐标 x 处取值的最小值；无直线返回 None。"""
        self._check_x(x)
        if not self._lines:
            return None
        best = None
        for line in self._lines:
            v = line.value_at(x)
            if best is None or v < best:
                best = v
        return best

    def query_max(self, x):
        """全部直线在横坐标 x 处取值的最大值；无直线返回 None。"""
        self._check_x(x)
        if not self._lines:
            return None
        best = None
        for line in self._lines:
            v = line.value_at(x)
            if best is None or v > best:
                best = v
        return best

    def query_argmin(self, x):
        """取到最小值的直线标识；并列取插入序号较小者。无直线返回 None。"""
        self._check_x(x)
        if not self._lines:
            return None
        best_line = self._lines[0]
        best = best_line.value_at(x)
        for line in self._lines[1:]:
            v = line.value_at(x)
            if v < best or (v == best and line.ident < best_line.ident):
                best = v
                best_line = line
        return best_line.ident

    def query_argmax(self, x):
        """取到最大值的直线标识；并列取插入序号较小者。无直线返回 None。"""
        self._check_x(x)
        if not self._lines:
            return None
        best_line = self._lines[0]
        best = best_line.value_at(x)
        for line in self._lines[1:]:
            v = line.value_at(x)
            if v > best or (v == best and line.ident < best_line.ident):
                best = v
                best_line = line
        return best_line.ident

    def range_min(self, l, r):
        """半开区间 [l, r) 内整数横坐标上的最小值；无整数点或无直线返回 None。

        朴素实现把区间内的每一个整数横坐标逐个点名，每个点再逐条求值。
        """
        self._check_range(l, r)
        if not self._lines:
            return None
        lo = max(l, self._lo)
        hi = min(r, self._hi)
        best = None
        for x in range(lo, hi):
            for line in self._lines:
                v = line.value_at(x)
                if best is None or v < best:
                    best = v
        return best

    def all_values(self, x):
        """返回全部直线在横坐标 x 处的取值列表，按插入先后排列。"""
        self._check_x(x)
        return [line.value_at(x) for line in self._lines]

    # ---- 内部 ----------------------------------------------------------

    def _as_int(self, v, name):
        if isinstance(v, bool) or not isinstance(v, int):
            raise IllegalArgument(name + "必须是整数")
        return int(v)

    def _check_x(self, x):
        if isinstance(x, bool) or not isinstance(x, int):
            raise IllegalArgument("横坐标必须是整数")
        if x < self._lo or x > self._hi:
            raise IllegalArgument("横坐标越出定义域")

    def _check_range(self, l, r):
        for x in (l, r):
            if isinstance(x, bool) or not isinstance(x, int):
                raise IllegalArgument("区间端点必须是整数")
        if l > r:
            raise IllegalArgument("区间左端大于右端")
        if l < self._lo or r > self._hi:
            raise IllegalArgument("区间越出定义域")
