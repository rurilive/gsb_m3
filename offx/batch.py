"""序列上的朴素离线批处理层。

当前只有一个 QueryBatch：持有一份不可变的元素序列，把一批区间查询逐条
处理。每一条查询都现场从头扫描它自己的那一段，逐位置累加或取极值，既没有
把查询按端点排序，也没有把上一条查询的结果复用到下一条，查询之间完全独立。
区间和、区间不同元素个数、区间内指定类的计数这三类统计都靠同一套重扫实现，
元素规模与查询条数一大，总代价就是查询条数乘以区间长度。
"""


class QueryBatch:
    """持有一份元素序列与一批区间查询，逐查询现场重扫。

    查询以 (left, right) 闭区间给出，下标从零起，含义是序列上左右闭区间内的
    元素。序列在构造时定下，之后不再变动。
    """

    def __init__(self, values):
        self._values = list(values)
        self._scans = 0

    # --- 基本属性 ---

    def size(self):
        """返回序列长度。"""
        return len(self._values)

    @property
    def scan_count(self):
        """自上次归零以来，逐元素重扫的总次数。"""
        return self._scans

    def reset_scan_count(self):
        """把重扫计数归零。"""
        self._scans = 0

    # --- 内部 ---

    def _check(self, left, right):
        n = len(self._values)
        if not isinstance(left, int) or not isinstance(right, int):
            raise ValueError("区间端点必须是整数")
        if left < 0 or right < 0 or left > right or right >= n:
            raise ValueError("非法区间: %r, %r" % (left, right))

    def _walk(self, left, right):
        """逐位置走过闭区间，返回这一段的元素副本列表。"""
        out = []
        for i in range(left, right + 1):
            self._scans += 1
            out.append(self._values[i])
        return out

    # --- 查询 ---

    def range_sum(self, left, right):
        """逐查询重扫闭区间求元素和。"""
        self._check(left, right)
        total = 0
        for v in self._walk(left, right):
            total += v
        return total

    def range_distinct(self, left, right):
        """逐查询重扫闭区间数不同元素个数。"""
        self._check(left, right)
        seen = set()
        for v in self._walk(left, right):
            seen.add(v)
        return len(seen)

    def range_count_class(self, left, right, klass):
        """逐查询重扫闭区间数等于指定类的元素个数。"""
        self._check(left, right)
        total = 0
        for v in self._walk(left, right):
            if v == klass:
                total += 1
        return total


def answer_queries(values, queries, mode):
    """对一批查询逐条现场重扫给出答案，返回与输入同序的答案列表。

    queries 里每项是 (left, right)；mode 取 sum、distinct 或 count_k，count_k
    时每项写成 (left, right, klass)。
    """
    batch = QueryBatch(values)
    out = []
    for q in queries:
        if mode == "sum":
            out.append(batch.range_sum(q[0], q[1]))
        elif mode == "distinct":
            out.append(batch.range_distinct(q[0], q[1]))
        elif mode == "count_k":
            out.append(batch.range_count_class(q[0], q[1], q[2]))
        else:
            raise ValueError("未知的统计模式: %r" % (mode,))
    return out


def scan_visits(queries):
    """按逐查询重扫的口径，估算这批查询一共要走多少个元素位置。"""
    total = 0
    for q in queries:
        total += q[1] - q[0] + 1
    return total
