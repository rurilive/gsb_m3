"""bit2d 的朴素逐格累加实现（改造前的现状）。

现在只有这一条路：一个二维网格工具。点更新就是把某个格子直接改掉，
子矩阵求和就是把这个矩形里的每个格子挨个拿出来累加一遍。
没有二维树状数组，没有二维前缀和数组的重建，也没有差分，
也不存在把矩形面积降下来的任何索引结构。
"""


def _is_int(v):
    """bool 不算整数，只有真正的 int 才算。"""
    return isinstance(v, int) and not isinstance(v, bool)


class NaiveGrid:
    """一个二维整数网格，子矩阵求和只有逐格累加这一种做法。"""

    def __init__(self, rows, cols, values=None):
        """按行列数建一张网格，初始全为零；values 给出时按行优先铺进去。"""
        if not _is_int(rows) or not _is_int(cols):
            raise ValueError("rows and cols must be ints")
        if rows < 0 or cols < 0:
            raise ValueError("rows and cols must be non-negative")
        self._rows = rows
        self._cols = cols
        self._data = [[0] * cols for _ in range(rows)]
        self._last_cost = 0
        self._last_rebuilds = 0
        if values is not None:
            self._load(values)

    def shape(self):
        """返回 (行数, 列数)。"""
        return (self._rows, self._cols)

    def value_at(self, row, col):
        """取回某个格子的当前值，越界报 IndexError。"""
        self._check_cell(row, col)
        return self._data[row][col]

    def to_matrix(self):
        """返回底层数据的一份行优先副本，改动副本不影响网格。"""
        return [list(r) for r in self._data]

    def update(self, row, col, delta):
        """把某个格子加上增量 delta，返回加完之后的新值，越界报 IndexError。"""
        self._check_cell(row, col)
        if not _is_int(delta):
            raise ValueError("delta must be an int")
        self._data[row][col] += delta
        return self._data[row][col]

    def query(self, row1, col1, row2, col2):
        """返回子矩阵 [row1, row2] x [col1, col2] 的元素和，半开区间。

        这一步把这个矩形里的每个格子都摸一遍再累加，摸过几个格子就是几个
        格子的代价，矩形一大就白扫，摸过的格子数记在 last_cost() 里方便观察。
        空矩形返回 0，行或列区间左端不小于右端时也返回 0。
        """
        self._check_rectangle(row1, col1, row2, col2)
        total = 0
        self._last_cost = 0
        for r in range(row1, row2):
            rowline = self._data[r]
            for c in range(col1, col2):
                total += rowline[c]
                self._last_cost += 1
        return total

    def dense_prefix(self):
        """重建整张二维前缀和表，用 (rows + 1) x (cols + 1) 的行优先列表返回。

        这一步每次都由底层数据从零重算一遍，表的第 r 行第 c 列放的是从
        左上角到 (r, c) 之前这个矩形的和。它是另一条独立路子，只用来印证
        逐格累加的口径，不与别处互相调用。
        """
        rows, cols = self._rows, self._cols
        table = [[0] * (cols + 1) for _ in range(rows + 1)]
        for r in range(rows):
            base = table[r]
            cur = table[r + 1]
            line = self._data[r]
            for c in range(cols):
                cur[c + 1] = base[c + 1] + cur[c] - base[c] + line[c]
        return table

    def rebuild_snapshot(self):
        """在当前数据上重做一次二维前缀和表，返回它的行优先副本。

        与 dense_prefix 同口径，但每次调用都当作从零开始的一次重建，
        方便观察每改一个格子就要把整张表重做一遍这件事。
        """
        self._last_rebuilds += 1
        return self.dense_prefix()

    def last_cost(self):
        """返回上一次 query 摸过的格子个数。"""
        return self._last_cost

    def rebuild_count(self):
        """返回 rebuild_snapshot 累计被调用过的次数。"""
        return self._last_rebuilds

    def _load(self, values):
        flat = list(values)
        need = self._rows * self._cols
        if len(flat) != need:
            raise ValueError("values length must be rows * cols")
        for v in flat:
            if not _is_int(v):
                raise ValueError("values must be ints")
        for r in range(self._rows):
            for c in range(self._cols):
                self._data[r][c] = flat[r * self._cols + c]

    def _check_cell(self, row, col):
        if not _is_int(row) or not _is_int(col):
            raise ValueError("row and col must be ints")
        if row < 0 or row >= self._rows:
            raise IndexError("row out of range: %r" % (row,))
        if col < 0 or col >= self._cols:
            raise IndexError("col out of range: %r" % (col,))

    def _check_rectangle(self, row1, col1, row2, col2):
        if not _is_int(row1) or not _is_int(col1):
            raise ValueError("corner must be an int")
        if not _is_int(row2) or not _is_int(col2):
            raise ValueError("corner must be an int")
        if row1 < 0 or col1 < 0:
            raise IndexError("corner out of range")
        if row2 > self._rows or col2 > self._cols:
            raise IndexError("corner out of range")
