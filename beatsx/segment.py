"""beatsx.segment：可变序列的区间操作（改造前的朴素实现）。

现状做法：内部只存一个普通列表，每一类区间操作都是最直白的写法。

- 区间取最小值（把落在区间里、数值超过某上界的元素压到上界）走的是逐元素
  比对再改写，区间里每个位置都要读一遍，超过上界的当场写回去；
- 区间加与区间赋值同样从区间左端点走到右端点，逐元素累加或覆盖；
- 区间求和与区间最值则是切出这一段之后逐元素累加、逐项取极值。

这套写法结果是对的，一眼能看穿，但每个操作都要把整段走一遍：取最小值这种
能把一大片元素整体压低的场合也不例外，规模一上来就全是白扫。
"""


class SegmentError(Exception):
    """beatsx 全部异常的共同基类。"""


class BadRangeError(SegmentError):
    """区间端点非法：越界或者左端点大于右端点。"""


class BadValueError(SegmentError):
    """传入的数值不是整数（布尔量也一并拒绝）。"""


class EmptySeqError(SegmentError):
    """在空序列上求极值，结果无法定义。"""


class BeatsSeq:
    """可变整数序列，支持区间取最小值、区间加、区间赋值与区间查询。

    全部区间都按左闭右开口径解释，左端点小于右端点，空序列上没有可取
    的极值。每次操作都在原序列上就地改写，不返回副本。第几次操作就是
    操作序号，从零起算，取最小值之外的每类操作在返回里附带该序号。
    """

    def __init__(self, values):
        self._data = [self._int(v) for v in values]
        self._op_count = 0

    @staticmethod
    def _int(v):
        if not isinstance(v, int) or isinstance(v, bool):
            raise BadValueError("expected an int, got %r" % (type(v).__name__,))
        return v

    def _check(self, lo, hi):
        """左闭右开区间检查，非法一律立刻报错。"""
        self._int(lo)
        self._int(hi)
        n = len(self._data)
        if lo < 0 or hi > n or lo > hi:
            raise BadRangeError("range [%r, %r) out of range" % (lo, hi))

    def values(self):
        """整份数据的浅拷贝，改它不影响内部序列。"""
        return list(self._data)

    def __len__(self):
        return len(self._data)

    def op_count(self):
        """已经执行过的操作次数。"""
        return self._op_count

    def range_chmin(self, lo, hi, upper):
        """区间取最小值：把 [lo, hi) 里超过 upper 的元素压到 upper。

        基线做法：从 lo 走到 hi，逐元素比对，超界的当场改写。改写时把每
        个被改位置的数值差累加起来一并返回，没被改的记零。
        """
        self._check(lo, hi)
        upper = self._int(upper)
        dropped = 0
        for i in range(lo, hi):
            if self._data[i] > upper:
                dropped += self._data[i] - upper
                self._data[i] = upper
        self._op_count += 1
        return dropped

    def range_add(self, lo, hi, delta):
        """区间加：把 [lo, hi) 里每个元素加上 delta。"""
        self._check(lo, hi)
        delta = self._int(delta)
        for i in range(lo, hi):
            self._data[i] += delta
        self._op_count += 1
        return self._op_count

    def range_assign(self, lo, hi, value):
        """区间赋值：把 [lo, hi) 里每个元素覆盖成 value。"""
        self._check(lo, hi)
        value = self._int(value)
        for i in range(lo, hi):
            self._data[i] = value
        self._op_count += 1
        return self._op_count

    def range_sum(self, lo, hi):
        """区间求和：逐元素累加 [lo, hi)。"""
        self._check(lo, hi)
        total = 0
        for i in range(lo, hi):
            total += self._data[i]
        return total

    def range_qmin(self, lo, hi):
        """区间最小值：逐元素取最小，空序列或空区间上无定义。"""
        self._check(lo, hi)
        if not self._data or lo == hi:
            raise EmptySeqError("no extremum over an empty span")
        return min(self._data[lo:hi])

    def range_qmax(self, lo, hi):
        """区间最大值：逐元素取最大，空序列或空区间上无定义。"""
        self._check(lo, hi)
        if not self._data or lo == hi:
            raise EmptySeqError("no extremum over an empty span")
        return max(self._data[lo:hi])

    def touched(self):
        """按当前数据推算的访问量统计快照。

        基线每次操作都要走满整段：把元素总数当作访问次数，被改写次数按
        零算（它没有为取最小值单独记账）。子类与改造后的实现会覆盖它。
        """
        return {
            "nodes": len(self._data),
            "rewritten": 0,
        }
