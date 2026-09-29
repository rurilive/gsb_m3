"""区间集的朴素查询层。

当前只有一份 RangeSet 与两次线性扫描查询 scan_point 与 scan_interval：
每次查询都把全部区间逐个走一遍判相交，没有任何有序结构，也没有剪枝，
增删、合并、覆盖统计这些能力都还没有入口。
"""


class Interval:
    """闭区间 [left, right]，两端都算在内。"""

    __slots__ = ("left", "right")

    def __init__(self, left, right):
        if left > right:
            raise ValueError(
                "interval left must not exceed right: %r > %r" % (left, right)
            )
        self.left = left
        self.right = right

    def __eq__(self, other):
        return (
            isinstance(other, Interval)
            and self.left == other.left
            and self.right == other.right
        )

    def __hash__(self):
        return hash((self.left, self.right))

    def __repr__(self):
        return "Interval(%r, %r)" % (self.left, self.right)


class RangeSet:
    """一组闭区间的集合，查询靠线性扫描。"""

    def __init__(self):
        self._items = []
        self._access = 0

    # --- 写入 ---

    def insert(self, left, right):
        """把闭区间 [left, right] 追加进来，返回落库后的区间副本。"""
        iv = Interval(left, right)
        self._items.append(iv)
        return Interval(iv.left, iv.right)

    # --- 基本属性 ---

    def __len__(self):
        return len(self._items)

    def count(self):
        """返回区间个数。"""
        return len(self._items)

    def intervals(self):
        """返回全部区间的副本列表，当前为加入顺序。"""
        return [Interval(iv.left, iv.right) for iv in self._items]

    # --- 访问计数 ---

    @property
    def access_count(self):
        """自上次归零以来，查询逐个走过的区间数。"""
        return self._access

    def reset_access_count(self):
        """把访问计数归零。"""
        self._access = 0

    # --- 查询 ---

    def scan_point(self, point):
        """线性扫描：返回包含该点的全部区间，保持加入顺序。"""
        out = []
        for iv in self._items:
            self._access += 1
            if iv.left <= point <= iv.right:
                out.append(Interval(iv.left, iv.right))
        return out

    def scan_interval(self, left, right):
        """线性扫描：返回与 [left, right] 相交的全部区间，保持加入顺序。"""
        if left > right:
            raise ValueError(
                "query left must not exceed right: %r > %r" % (left, right)
            )
        out = []
        for iv in self._items:
            self._access += 1
            if iv.left <= right and left <= iv.right:
                out.append(Interval(iv.left, iv.right))
        return out
