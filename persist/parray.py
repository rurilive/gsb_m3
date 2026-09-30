"""可持久化数组（改造前的朴素基线）。

每次单点修改都把整份数组拷贝一份存成新版本，历史查询按键取出对应整份快照。
规模一大，每次修改都要线性拷贝，版本一多内存就平方增长。
所有运算只走整数与元组，不碰浮点，也不依赖任何第三方库。
"""


class Erro(Exception):
    """本库所有错误的基类，外部只认它即可兜住全部异常。"""


class BadArgument(Erro):
    """构造或调用时传入了非法的参数。"""


class VersionOutOfRange(Erro):
    """版本号越界，或版本区间的两端次序颠倒。"""


class IndexOutOfRange(Erro):
    """下标越界。"""


class KthOutOfRange(Erro):
    """要求第 k 小时，k 超出该版本区间可取的个数范围。"""


class PersistentArray:
    """朴素可持久化数组。

    版本零是初始空版本，长度为 length，每个位置都取填充值 fill。
    modify 在某个既有版本上做一次单点修改，把整份数组拷一份存成新版本，
    新版本的编号是现有版本数。query 按键取出某个版本的某个位置。
    kth 统计某段版本区间内各次修改写入的值，返回其中第 k 小。
    """

    def __init__(self, length, fill=0):
        if not isinstance(length, int) or length < 0:
            raise BadArgument("数组长度必须是非负整数")
        self._length = length
        self._fill = fill
        self._snapshots = [tuple([fill]) * length]
        self._writes = [None]

    @property
    def length(self):
        """数组长度。"""
        return self._length

    def version_count(self):
        """当前已有的版本个数，编号从零到版本数减一。"""
        return len(self._snapshots)

    def latest_version(self):
        """最近一次修改产生的版本编号。"""
        return len(self._snapshots) - 1

    def _check_version(self, version):
        if not isinstance(version, int) or version < 0 or version >= len(self._snapshots):
            raise VersionOutOfRange("版本号越界: %r" % (version,))

    def _check_index(self, index):
        if not isinstance(index, int) or index < 0 or index >= self._length:
            raise IndexOutOfRange("下标越界: %r" % (index,))

    def modify(self, version, index, value):
        """在版本 version 上把下标 index 改成 value，返回新版本号。

        朴素做法：把该版本的整份快照抄一份，改掉一个位置，追加成新版本。
        """
        self._check_version(version)
        self._check_index(index)
        snap = list(self._snapshots[version])
        snap[index] = value
        self._snapshots.append(tuple(snap))
        self._writes.append(value)
        return len(self._snapshots) - 1

    def query(self, version, index):
        """取出版本 version 下标 index 处的值。"""
        self._check_version(version)
        self._check_index(index)
        return self._snapshots[version][index]

    def snapshot(self, version):
        """取出某个版本的整份数组快照，返回元组。"""
        self._check_version(version)
        return self._snapshots[version]

    def kth(self, version_lo, version_hi, k):
        """版本区间 (version_lo, version_hi] 内各次修改写入值的第 k 小。

        区间是左开右闭：只统计版本号落在 version_lo 加一到 version_hi 之间的
        那些修改各自写入的值，凑成一个多重集合，再取第 k 小，k 从一起算。
        朴素做法：把这些写入值收集起来排序后直取。
        """
        self._check_version(version_lo)
        self._check_version(version_hi)
        if version_hi < version_lo:
            raise VersionOutOfRange("版本区间两端次序颠倒: %r %r" % (version_lo, version_hi))
        writes = [w for w in self._writes[version_lo + 1: version_hi + 1] if w is not None]
        writes.sort()
        if not isinstance(k, int) or k < 1 or k > len(writes):
            raise KthOutOfRange("第 k 小的 k 越界: %r 共 %d 个" % (k, len(writes)))
        return writes[k - 1]
