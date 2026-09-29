"""若干列凑成的朴素列存储。

现有能力：按列名放若干列，能整列取回、按行下标取一行、问行数列数与存储总量。
列编码、惰性解码、区间扫描、谓词下推与行更新尚未提供。
"""

from colstore.column import Column


class Store:
    """具名列存储。

    columns 是若干 Column，按首次出现的顺序推导列序。所有列的长度必须相等，
    不等就在构造处报错。表在构造时把列收进私有字典，之后对外只读。
    """

    def __init__(self, columns):
        if not isinstance(columns, (list, tuple)) or not columns:
            raise ValueError("columns must be a non-empty sequence")
        self._columns = {}
        self._order = []
        width = None
        for col in columns:
            if not isinstance(col, Column):
                raise ValueError("each column must be a Column")
            if col.name in self._columns:
                raise ValueError("duplicate column name: %s" % col.name)
            if width is None:
                width = len(col)
            elif len(col) != width:
                raise ValueError("all columns must have the same length")
            self._columns[col.name] = col
            self._order.append(col.name)

    @property
    def column_names(self):
        return tuple(self._order)

    def num_rows(self):
        return len(self._columns[self._order[0]])

    def get_column(self, name):
        """按列名取一列，列名不存在报 ValueError。"""
        if name not in self._columns:
            raise ValueError("no such column: %s" % name)
        return self._columns[name]

    def get_value(self, name, row):
        """按列名与行下标取单个值。"""
        return self.get_column(name).get(row)

    def get_row(self, row):
        """按行下标取一行，返回列名到值的字典。"""
        return dict((name, self._columns[name].get(row)) for name in self._order)

    def scan(self, name):
        """整列原样取回，返回一份新的列表。"""
        return self.get_column(name).to_list()

    def storage_size(self):
        """存储总量，等于各列存储占用之和。"""
        return sum(self._columns[name].storage_size() for name in self._order)

    def __repr__(self):
        return "Store(columns=%s, rows=%d)" % (self.column_names, self.num_rows())