"""sparsem 的现有实现：最朴素的稠密矩阵。

所有元素（含零）按行列顺序原样存在一个 list 的 list 里，
没有压缩、没有省略，读写都直接落到对应的格子上。
"""


class DenseMatrix:
    """稠密矩阵：内部就是一个 rows x cols 的嵌套列表，零元素也照存。

    DenseMatrix(rows, cols, data)   data 是嵌套可迭代，逐行逐列填入
    rows() / cols()                 形状
    get(i, j)                       读单个元素
    set(i, j, value)                写单个元素
    to_dense()                      返回嵌套列表副本
    equals(other)                   按元素逐位比较
    """

    def __init__(self, rows, cols, data):
        if not isinstance(rows, int) or not isinstance(cols, int):
            raise TypeError("rows 与 cols 必须是整数")
        if rows < 0 or cols < 0:
            raise ValueError("rows 与 cols 不能为负")
        grid = []
        for i in range(rows):
            row = []
            for j in range(cols):
                row.append(data[i][j])
            grid.append(row)
        self._rows = rows
        self._cols = cols
        self._grid = grid

    def rows(self):
        return self._rows

    def cols(self):
        return self._cols

    def get(self, i, j):
        self._check_index(i, j)
        return self._grid[i][j]

    def set(self, i, j, value):
        self._check_index(i, j)
        self._grid[i][j] = value
        return self

    def to_dense(self):
        return [list(row) for row in self._grid]

    def equals(self, other):
        if self._rows != other.rows() or self._cols != other.cols():
            return False
        for i in range(self._rows):
            for j in range(self._cols):
                if self._grid[i][j] != other.get(i, j):
                    return False
        return True

    def _check_index(self, i, j):
        if not (0 <= i < self._rows) or not (0 <= j < self._cols):
            raise IndexError(f"下标越界: ({i}, {j})")
