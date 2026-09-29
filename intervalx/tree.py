"""区间集合的朴素实现。

FlatIntervals 维护一组半开区间 ``[l, r)``，每个区间带一个标识。
所有查询（相交、点命中）都逐条扫描整个集合，合并也在全量排序后线性进行。
这是区间索引改造前的基线：行为被 tests/test_tree.py 锁住，改造后不得改变。
"""


class IntervalError(Exception):
    """intervalx 的异常基类，所有对外抛出的异常都继承它。"""


class InvalidInterval(IntervalError):
    """区间端点非法：左端点大于右端点。"""


class FlatIntervals:
    """一组半开区间 ``[l, r)``，标识唯一，线性扫描实现。

    端点口径：

    - 区间是半开的，左端点闭合、右端点开放，即 ``x`` 命中当且仅当 ``l <= x < r``。
    - 两条区间相交（作为点集有公共点）当且仅当 ``a < d`` 且 ``c < b``，
      因此仅端点相接（如 ``[1, 2)`` 与 ``[2, 3)``）不算相交。
    - 左右端点相等（``l == r``）的退化区间是空点集，不命中任何点，也不与任何区间相交。
    - 合并（merge_all）时，重叠与仅端点相接的区间都并成一段；退化区间单独保留。
    """

    def __init__(self):
        # 标识 -> (l, r)，字典保持插入顺序，遍历顺序是确定的。
        self._items = {}

    def __len__(self):
        return len(self._items)

    def __contains__(self, name):
        return name in self._items

    def add(self, l, r, name):
        """加入一条区间；同名标识覆盖旧值。左端点大于右端点时立即报错。"""
        if l > r:
            raise InvalidInterval("左端点不能大于右端点: %r > %r" % (l, r))
        self._items[name] = (l, r)

    def remove(self, name):
        """按键移除一条区间，删到返回 True，不存在返回 False。"""
        if name in self._items:
            del self._items[name]
            return True
        return False

    def names(self):
        """返回全部标识，保持插入顺序。"""
        return list(self._items.keys())

    def intervals(self):
        """返回 ``(l, r, name)`` 列表，保持插入顺序。"""
        return [(l, r, name) for name, (l, r) in self._items.items()]

    def overlaps(self, l, r):
        """线性扫描返回与 ``[l, r)`` 相交的全部标识。

        查询区间本身是空点集（``l == r``）时不与任何区间相交，返回空列表。
        """
        if l > r:
            raise InvalidInterval("左端点不能大于右端点: %r > %r" % (l, r))
        if l == r:
            return []
        hit = []
        for name, (a, b) in self._items.items():
            if a < r and l < b:
                hit.append(name)
        return hit

    def point_hit(self, x):
        """线性扫描返回覆盖点 ``x`` 的全部标识，口径为 ``l <= x < r``。"""
        hit = []
        for name, (a, b) in self._items.items():
            if a <= x < b:
                hit.append(name)
        return hit

    def merge_all(self):
        """线性合并全部区间，返回不相交的 ``(l, r)`` 列表。

        先按左端点排序，再从头到尾扫描：新一段的左端点小于等于当前段右端点
        （重叠或仅端点相接）就并入当前段，否则另起一段。退化区间单独保留。
        """
        ordered = sorted((a, b) for a, b in self._items.values())
        merged = []
        for a, b in ordered:
            if merged and a <= merged[-1][1]:
                last_l, last_r = merged[-1]
                if b > last_r:
                    merged[-1] = (last_l, b)
            else:
                merged.append((a, b))
        return merged
