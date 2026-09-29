"""内存表的朴素查询层。

当前只有一张行式内存表 Table 与一次线性扫描查询 scan：谓词逐条记录判断，
整张表都要走一遍，没有任何二级索引，范围查询与前缀查询都没有入口。
"""


class Table:
    """具名行式内存表，记录以字典存放，主键默认为 id 字段。"""

    def __init__(self, name, pk="id", fields=None):
        self.name = name
        self.pk = pk
        self._fields = list(fields) if fields else []
        self._rows = []
        self._access = 0

    # --- 写入 ---

    def insert(self, record):
        """追加一条记录，返回落库后的字典副本。"""
        row = dict(record)
        for key in row:
            if key not in self._fields:
                self._fields.append(key)
        self._rows.append(row)
        return dict(row)

    # --- 基本属性 ---

    def count(self):
        """返回记录条数。"""
        return len(self._rows)

    @property
    def fields(self):
        """按出现顺序返回字段名副本。"""
        return list(self._fields)

    def all(self):
        """返回全部记录的副本列表，保持插入顺序。"""
        return [dict(row) for row in self._rows]

    # --- 访问计数 ---

    @property
    def access_count(self):
        """自上次归零以来，查询逐条走过的记录数。"""
        return self._access

    def reset_access_count(self):
        """把访问计数归零。"""
        self._access = 0

    # --- 查询 ---

    def scan(self, predicate):
        """线性扫描：对每一条记录判断谓词，返回命中记录的副本列表。

        不管谓词用得到哪些字段，整张表都要过一遍，访问计数加的就是表的行数。
        结果保持插入顺序。
        """
        out = []
        for row in self._rows:
            self._access += 1
            if predicate(row):
                out.append(dict(row))
        return out
