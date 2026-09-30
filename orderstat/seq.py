"""Selector: 平铺列表上的朴素次序统计选择器（改造前基线）。

内部只有一份平铺的 list，元素按构造给出的顺序保存，允许负数与重复值。
所有查询都靠整段复制后全排序来完成：

- select_kth(rank)：把整段复制一份再排序，取排序后第 rank 个
- smallest_sum(count)：把整段排序，取前 count 个逐项累加成和
- median()：把整段排序，按长度取中间那个或中间两个的均值
- pairwise_median(other)：合并两份有序序列，再按长度取中位数
- replay(values, queries)：依次回放一串查询，返回逐步返回值

排序一律用标准库内置的稳定排序，不自己写。排名从 0 数起，即 k 等于 0 取
排序后最小的那个。规模一大，每个查询都要整段排序一次，中间没有任何可复用
的结构；一次查询碰过多少个元素也没有对外暴露。上述结果本身是对的。
"""


class OrderStatError(Exception):
    """orderstat 里所有可预期错误的基类。"""


class RankOutOfRangeError(OrderStatError):
    """排名越界或排名非法。"""


class EmptySequenceError(OrderStatError):
    """对空序列求次序统计量。"""


class Selector:
    """平铺列表上的朴素次序统计选择器。"""

    def __init__(self, values=()):
        """用 values 建实例，内部存一份副本。"""
        self._data = list(values)

    # -- 只读视图 ---------------------------------------------------------

    @property
    def data(self):
        """返回内部序列的副本。"""
        return list(self._data)

    def size(self):
        """序列长度。"""
        return len(self._data)

    # -- 内部校验 ---------------------------------------------------------

    def _check_empty(self):
        """空序列做次序统计就直接失败，非法就地快速失败。"""
        if not self._data:
            raise EmptySequenceError("空序列没有次序统计量")

    def _check_rank(self, rank):
        """检查排名 rank 是否落在 [0, n) 内，非法就地快速失败。"""
        n = len(self._data)
        if not isinstance(rank, int) or isinstance(rank, bool):
            raise RankOutOfRangeError("排名必须是整数: %r" % (rank,))
        if not (0 <= rank < n):
            raise RankOutOfRangeError("排名越界: %r 不在 [0, %d)" % (rank, n))
        return rank

    # -- 朴素次序统计 -----------------------------------------------------

    def sorted_copy(self):
        """把整段复制一份再排序后返回，供内部复用。"""
        return sorted(self._data)

    def select_kth(self, rank):
        """第 rank 个最小元素：整段复制排序后取第 rank 个。"""
        self._check_empty()
        rank = self._check_rank(rank)
        ordered = sorted(self._data)
        return ordered[rank]

    def smallest_sum(self, count):
        """前 count 个最小元素之和：整段排序后取前 count 个逐项累加。"""
        if not isinstance(count, int) or isinstance(count, bool):
            raise RankOutOfRangeError("个数必须是整数: %r" % (count,))
        if count < 0:
            raise RankOutOfRangeError("个数不能为负: %r" % (count,))
        if count > len(self._data):
            raise RankOutOfRangeError(
                "个数超出长度: %r 大于 %d" % (count, len(self._data))
            )
        ordered = sorted(self._data)
        total = 0
        for i in range(count):
            total += ordered[i]
        return total

    def median(self):
        """中位数：整段排序后按长度取中间一个或中间两个的均值。"""
        self._check_empty()
        ordered = sorted(self._data)
        return self._median_of_sorted(ordered)

    @staticmethod
    def _median_of_sorted(ordered):
        """在已排序序列上取中位数，偶数长度取中间两个的均值。"""
        n = len(ordered)
        mid = n // 2
        if n % 2 == 1:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2

    def pairwise_median(self, other):
        """两个序列的中位数：各自排序后归并合并，再取整体中位数。"""
        left = sorted(self._data)
        right = sorted(list(other))
        merged = Selector._merge_sorted(left, right)
        self._check_empty_seq(merged)
        return Selector._median_of_sorted(merged)

    @staticmethod
    def _check_empty_seq(seq):
        """合并结果为空就没有中位数。"""
        if not seq:
            raise EmptySequenceError("空序列没有中位数")

    @staticmethod
    def _merge_sorted(left, right):
        """把两份已排序序列归并成一份有序序列，逐项比较。"""
        merged = []
        i = 0
        j = 0
        while i < len(left) and j < len(right):
            if left[i] <= right[j]:
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
        while i < len(left):
            merged.append(left[i])
            i += 1
        while j < len(right):
            merged.append(right[j])
            j += 1
        return merged

    # -- 查询回放 ---------------------------------------------------------

    @staticmethod
    def replay(values, queries):
        """按 queries 依次回放，返回 (末态, 每步返回值) 二元组。

        每个查询是一个元组，首项是查询名，后面是参数：

        - ("kth", rank)         -> 第 rank 个最小元素
        - ("smallest", count)   -> 前 count 个最小元素之和
        - ("median",)           -> 中位数
        - ("pairwise", other)   -> 与 other 合并后的中位数

        回放在 values 的一份副本上进行，返回的末态是那份副本本身。
        """
        if isinstance(values, Selector):
            work = Selector(values.data)
        else:
            work = Selector(values)
        results = []
        for query in queries:
            name = query[0]
            args = query[1:]
            if name == "kth":
                results.append(work.select_kth(*args))
            elif name == "smallest":
                results.append(work.smallest_sum(*args))
            elif name == "median":
                results.append(work.median())
            elif name == "pairwise":
                results.append(work.pairwise_median(*args))
            else:
                raise OrderStatError("未知查询: %r" % (name,))
        return work.data, results
