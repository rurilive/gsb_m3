"""pst: 朴素可版本化计数结构（改造前基线）。

FlatCtl 内部只维护一个计数数组。每次更新都对整份数组做一次拷贝，
历史版本也只是把当时的整份数组原样存下来。这里是改造前的朴素实现，
没有线段树、没有节点共享，也没有对数级的查询路径。
"""


class PstError(Exception):
    """pseg 的异常基类。"""


class PstIndexError(PstError):
    """非法下标。"""


class FlatCtl:
    """朴素可版本化计数结构。

    用 size 个位置保存整数计数，取值约定落在闭区间零到 max_value。
    每次 add 都把整份数组拷贝一份返回，snapshot 存下的也是整份拷贝，
    因此版本一多内存就线性膨胀。
    """

    def __init__(self, size, max_value=None):
        if size < 0:
            raise PstError("size 不能为负")
        if max_value is None:
            max_value = size
        if max_value < 0:
            raise PstError("max_value 不能为负")
        self._size = size
        self._max_value = max_value
        self._data = [0] * size
        self._snapshots = [list(self._data)]

    # ---- 结构读取 ----

    @property
    def size(self):
        return self._size

    @property
    def max_value(self):
        return self._max_value

    def __len__(self):
        return self._size

    def values(self):
        """返回当前数组的一份拷贝。"""
        return list(self._data)

    def _check_index(self, i):
        if isinstance(i, bool) or not isinstance(i, int):
            raise PstIndexError(i)
        if i < 0 or i >= self._size:
            raise PstIndexError(i)

    # ---- 更新 ----

    def add(self, i, delta):
        """对下标 i 加增量 delta，返回新数组的一份拷贝。"""
        self._check_index(i)
        self._data[i] += delta
        return list(self._data)

    # ---- 版本 ----

    def snapshot(self):
        """把当前整份数组原样存为一个版本，返回版本号。"""
        self._snapshots.append(list(self._data))
        return len(self._snapshots) - 1

    def version_count(self):
        return len(self._snapshots)

    def point(self, i, version=None):
        """取下标 i 的当前取值；给定版本号则取该历史版本的取值。"""
        self._check_index(i)
        if version is None:
            return self._data[i]
        if isinstance(version, bool) or not isinstance(version, int):
            raise PstError("版本号非法")
        if version < 0 or version >= len(self._snapshots):
            raise PstError("版本号越界")
        return self._snapshots[version][i]

    # ---- 查询 ----

    def count_le(self, x):
        """统计取值不大于 x 的位置个数（线性扫描）。"""
        total = 0
        for v in self._data:
            if v <= x:
                total += 1
        return total

    def kth_ge(self, x):
        """返回第一个取值不小于 x 的下标；若没有则返回负一（线性扫描）。"""
        for i, v in enumerate(self._data):
            if v >= x:
                return i
        return -1
