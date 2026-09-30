"""mergeseq.mergeable：序列的区间统计（改造前的朴素实现）。

现状做法：内部只留一条当前序列。单点赋值就复制一份当前序列再改掉一个
位置；区间求和拿到原序列后从头扫过区间的每一个位置逐步累加；区间最值
同样从头扫过每一个位置逐步比较取极值；区间第几小则切出那一段整段排序
再按下标取。每一次查询都把这一段完整地重新走一遍，查询之间没有任何
复用，也没有任何挂在序列之上的加速结构。

这套做法结果是对的，规模小时一眼能看穿，但任何一次查询的代价都与区间
长度成正比：查一次就是一次整段扫描，连续查很多次就把同一段反复走了
很多遍，规模一上来就顶不住了。非法版本、越界下标、非法数值、空序列上
取极值，统一抛异常快速失败，绝不悄悄兜底也不擅自改小。
"""


class MergeableSegError(Exception):
    """mergeseq 全部异常的共同基类。"""


class VersionError(MergeableSegError):
    """版本号不存在或早于最初版本。"""


class IndexRangeError(MergeableSegError):
    """下标越界，属于调用方非法输入。"""


class EmptySeqError(MergeableSegError):
    """对空序列或空区间下达了无法定义结果的操作。"""


class MergeSeq:
    """序列的区间统计（基线：任何查询都从头扫过整段）。

    构造参数 initial 是初始序列，存成版本号为零的最初版本，也是所有版本
    的共同祖先。set 单点赋值返回新版本号，当前版本同时推进。version 返回
    当前版本号，use 把当前版本切到任意历史版本。range_sum 的左闭右开口径
    与切片一致，range_min 与 range_max 的左闭右闭口径、kth_smallest 的
    左闭右闭口径都以查询所在版本当时的数据为准。任何查询都在目标版本的
    那条序列上从头扫过区间逐步累加或比较，查询之间不复用任何中间结果。
    """

    def __init__(self, initial):
        self._versions = [list(initial)]
        self._current = 0
        self._scans = 0

    def _snapshot(self, version=None):
        """取版本快照：不给版本号就用当前版本。"""
        v = self._current if version is None else version
        if v < 0 or v >= len(self._versions):
            raise VersionError("no such version: %r" % (v,))
        return self._versions[v]

    def _check_value(self, value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise MergeableSegError("value must be an int, got %r"
                                    % (type(value).__name__,))

    def _check_span(self, data, lo, hi):
        """闭区间口径的下标检查，左闭右闭。空序列上没有可取的极值。"""
        if not data:
            raise EmptySeqError("no extremum over an empty sequence")
        if lo < 0 or hi >= len(data) or lo > hi:
            raise IndexRangeError("span [%r, %r] out of range" % (lo, hi))

    def size(self, version=None):
        """该版本的元素个数。"""
        return len(self._snapshot(version))

    def get(self, index, version=None):
        """该版本 index 处的值。"""
        data = self._snapshot(version)
        if index < 0 or index >= len(data):
            raise IndexRangeError("index %r out of range" % (index,))
        return data[index]

    def values(self, version=None):
        """该版本整份数据的拷贝，改它不影响任何版本。"""
        return list(self._snapshot(version))

    def set(self, index, value):
        """单点赋值，返回新版本号。

        基线做法：把当前版本那条序列整份复制一份，在副本上改掉一个位置，
        把副本追加成新版本并让当前版本指过去，旧版本那条原样保留。
        """
        data = self._snapshot()
        if index < 0 or index >= len(data):
            raise IndexRangeError("index %r out of range" % (index,))
        self._check_value(value)
        new_data = list(data)
        new_data[index] = value
        self._versions.append(new_data)
        self._current = len(self._versions) - 1
        return self._current

    def version(self):
        """当前版本号。"""
        return self._current

    def use(self, version):
        """把当前版本切到指定历史版本，返回切换后的版本号。"""
        self._snapshot(version)
        self._current = version
        return self._current

    def range_sum(self, lo, hi, version=None):
        """求 [lo, hi) 的和，左闭右开，与切片口径一致。

        基线做法：拿到那个版本的那条序列，从 lo 起逐个位置加到 hi 前为止，
        区间里每一个位置都要重新走一遍。
        """
        data = self._snapshot(version)
        if lo < 0 or hi > len(data) or lo > hi:
            raise IndexRangeError("range [%r, %r) out of range" % (lo, hi))
        total = 0
        for i in range(lo, hi):
            total += data[i]
            self._scans += 1
        return total

    def range_min(self, lo, hi, version=None):
        """求闭区间 [lo, hi] 的最小值，左闭右闭。"""
        return self._extremum(lo, hi, version, min)

    def range_max(self, lo, hi, version=None):
        """求闭区间 [lo, hi] 的最大值，左闭右闭。"""
        return self._extremum(lo, hi, version, max)

    def _extremum(self, lo, hi, version, pick):
        """基线做法：从 lo 起逐个位置比较到 hi，整段重新走一遍。"""
        data = self._snapshot(version)
        self._check_span(data, lo, hi)
        best = data[lo]
        for i in range(lo + 1, hi + 1):
            best = pick(best, data[i])
            self._scans += 1
        return best

    def kth_smallest(self, lo, hi, k, version=None):
        """闭区间 [lo, hi] 里第 k 小的值，k 从 1 起算。

        基线做法：切出这一段，排序，再取下标；整段重扫外加一次排序。
        """
        data = self._snapshot(version)
        self._check_span(data, lo, hi)
        seg = data[lo:hi + 1]
        count = len(seg)
        if not isinstance(k, int) or isinstance(k, bool) or k < 1 or k > count:
            raise IndexRangeError("k %r out of [1, %r]" % (k, count))
        self._scans += count
        seg.sort()
        return seg[k - 1]

    def taken(self):
        """快照计数：本实例以来所有区间查询累计走过的位置数。

        基线的访问计数：查一次区间就把区间里的位置从头走一遍，连续查同一
        段时这个数会反复增长，暴露的是查询之间零复用这一现状。
        """
        return self._scans

    def stats(self):
        """内存与版本计数快照，独立 dict，改它不影响实例。"""
        live = sum(len(d) for d in self._versions)
        return {
            "versions": len(self._versions),
            "size": len(self._versions[-1]),
            "live_values": live,
            "current": self._current,
            "scans": self._scans,
        }
