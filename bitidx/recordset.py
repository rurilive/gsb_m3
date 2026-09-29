"""一张具名列记录集与朴素全量扫描。

现有能力：按列名放若干列整数，插入行、删除行，按条件逐行判一遍得到命中的
行号集合，按行号取一行，问行数与列名。
位图索引、位运算组合查询、压缩位图、计数分页与排序键尚未提供。
"""


class RecordSet:
    """具名列记录集。

    columns 是列名到整数列表的字典，各列长度必须相等。
    行号是 0 起的连续下标，删除一行后它后面的行号依次前移。
    记录集在构造时校验每个值都是整数，值拷进私有列表，之后对外只读。
    """

    def __init__(self, columns):
        if not isinstance(columns, dict) or not columns:
            raise ValueError("columns must be a non-empty dict")
        self._columns = {}
        self._order = []
        width = None
        for name, values in columns.items():
            if not isinstance(name, str) or not name:
                raise ValueError("column name must be a non-empty string")
            copied = []
            for v in values:
                if not isinstance(v, int) or isinstance(v, bool):
                    raise ValueError("row values must be int")
                copied.append(v)
            if width is None:
                width = len(copied)
            elif len(copied) != width:
                raise ValueError("all columns must have the same length")
            self._columns[name] = copied
            self._order.append(name)

    @property
    def column_names(self):
        return tuple(self._order)

    def num_rows(self):
        return len(self._columns[self._order[0]])

    def _check_column(self, name):
        if name not in self._columns:
            raise ValueError("no such column: %s" % name)
        return self._columns[name]

    def get_value(self, name, row):
        """按列名与行号取一个值，列名不存在报 ValueError。"""
        column = self._check_column(name)
        return column[row]

    def get_row(self, row):
        """按行号取一行，返回列名到值的字典。"""
        return dict((name, self._columns[name][row]) for name in self._order)

    def scan(self, name):
        """整列取回，返回一份新的列表。"""
        return list(self._check_column(name))

    def select(self, name, value):
        """朴素全量扫描：逐行判断某列是否等于给定值，返回命中的行号集合。

        这是唯一的查询入口。它对每一行都取一次值、判一次条件，
        返回的行号升序去重，没有命中的时候返回空集合。
        """
        column = self._check_column(name)
        hits = []
        for row in range(len(column)):
            if column[row] == value:
                hits.append(row)
        return hits

    def insert(self, row):
        """在末尾插入一行，row 是列名到整数的字典，缺列或非整数立刻报错。"""
        if not isinstance(row, dict):
            raise ValueError("row must be a dict")
        if set(row.keys()) != set(self._order):
            raise ValueError("row must cover exactly the known columns")
        for name in self._order:
            v = row[name]
            if not isinstance(v, int) or isinstance(v, bool):
                raise ValueError("row values must be int")
        width = self.num_rows()
        for name in self._order:
            self._columns[name].append(row[name])
        return width

    def delete(self, row):
        """删除一行，其后行号依次前移，越界报 IndexError。"""
        width = self.num_rows()
        if row < 0 or row >= width:
            raise IndexError("row out of range")
        for name in self._order:
            del self._columns[name][row]

    def __repr__(self):
        return "RecordSet(columns=%s, rows=%d)" % (self.column_names, self.num_rows())