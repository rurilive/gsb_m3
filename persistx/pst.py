"""persistx.pst：序列的版本化统计（改造前的朴素实现）。

现状做法：内部维护版本列表，每个版本就是对数组的一份完整拷贝；单点修改
先把当前版本的数组整份复制出来，改掉一个位置，把副本追加成新版本，旧版本
那份数组原样不动。区间求和与区间最值就拿到目标版本的副本上切片再逐项累加、
逐项取极值；第几小就同样切片后排序取下标。求空区间和、空区间极值、越界
或者问一个还不存在的版本号，统一抛异常快速失败，绝不悄悄兜底或擅自改小。

这套做法结果是对的，规模小时一眼能看穿，但内存与时间都随修改次数线性上涨：
改一次就是一次整份拷贝，查一次就是一次整段扫描，版本一多就顶不住了。
"""


class PstError(Exception):
    """persistx 全部异常的共同基类。"""


class VersionError(PstError):
    """版本号不存在或早于初始版本。"""


class IndexRangeError(PstError):
    """下标越界，属于调用方非法输入。"""


class EmptySeqError(PstError):
    """对空序列下达了无法定义结果的操作。"""


class PersistSeq:
    """序列的版本化统计（基线：每次修改整份复制数组）。

    构造参数 initial 是初始序列，内部存成新版本，版本号为 0，也是所有
    版本的共同祖先。set 返回新版本号，当前版本同时推进。version 把当前
    版本切到任意历史版本，看着像是回退，但历史版本一个都不会丢。求和的
    左闭右开口径与切片一致，左闭右闭的最值口径与第几小口径都以查询所在
    版本当时的数据为准。
    """

    def __init__(self, initial):
        self._versions = [list(initial)]
        self._current = 0

    def _snapshot(self, version=None):
        """取版本快照：不给版本号就用当前版本。"""
        v = self._current if version is None else version
        if v < 0 or v >= len(self._versions):
            raise VersionError("no such version: %r" % (v,))
        return self._versions[v]

    def _check_value(self, value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise PstError("value must be an int, got %r" % (type(value).__name__,))

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

        基线做法：把当前版本的数组整份复制一份，在副本上改一个位置，把
        副本追加成新版本并让当前版本指过去。旧版本的数组没有被碰过。
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

        基线做法：拿到那个版本的数组，切出这一段，再逐项累加。
        """
        data = self._snapshot(version)
        if lo < 0 or hi > len(data) or lo > hi:
            raise IndexRangeError("range [%r, %r) out of range" % (lo, hi))
        total = 0
        for i in range(lo, hi):
            total += data[i]
        return total

    def range_min(self, lo, hi, version=None):
        """求闭区间 [lo, hi] 的最小值，左闭右闭。"""
        return self._extremum(lo, hi, version, min)

    def range_max(self, lo, hi, version=None):
        """求闭区间 [lo, hi] 的最大值，左闭右闭。"""
        return self._extremum(lo, hi, version, max)

    def _extremum(self, lo, hi, version, pick):
        data = self._snapshot(version)
        self._check_span(data, lo, hi)
        best = data[lo]
        for i in range(lo + 1, hi + 1):
            best = pick(best, data[i])
        return best

    def kth_smallest(self, lo, hi, k, version=None):
        """闭区间 [lo, hi] 里第 k 小的值，k 从 1 起算。

        基线做法：切出这一段，排序，再取下标；切片排序花的是平方级代价。
        """
        data = self._snapshot(version)
        self._check_span(data, lo, hi)
        seg = data[lo:hi + 1]
        if not seg:
            raise EmptySeqError("kth_smallest on empty segment")
        count = len(seg)
        if not isinstance(k, int) or isinstance(k, bool) or k < 1 or k > count:
            raise IndexRangeError("k %r out of [1, %r]" % (k, count))
        seg.sort()
        return seg[k - 1]

    def stats(self):
        """内存与版本计数快照，独立 dict，改它不影响实例。"""
        live = sum(len(d) for d in self._versions)
        return {
            "versions": len(self._versions),
            "size": len(self._versions[-1]),
            "live_values": live,
            "current": self._current,
        }
