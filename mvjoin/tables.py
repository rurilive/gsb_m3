"""内存表、数据集与变更流。

一张表有一个主键列，行是普通 dict。上游把每次变化包成一条变更，
按到达顺序喂给 ``Dataset.apply``：

    {"seq": 7, "table": "orders", "op": "insert", "before": None,  "after": {...}}
    {"seq": 8, "table": "orders", "op": "update", "before": {...}, "after": {...}}
    {"seq": 9, "table": "orders", "op": "delete", "before": {...}, "after": None}

seq 由上游发放、全局单调递增，同一条变更重发时 seq 不变。主键列的值不会变，
before 与 after 的主键一致；连接键之类的普通列随便改。数据集只管当前内容，
不做去重、不做重排，重复与乱序投递是投递侧的事。
"""

OPS = ("insert", "update", "delete")


class TableError(ValueError):
    """变更与表内容对不上。"""


class Table:
    """一张内存表，按主键存整行。拿出去的行都是副本，改不动表。"""

    def __init__(self, name, key):
        if not isinstance(name, str) or not name:
            raise TableError("表名必须是非空字符串")
        if not isinstance(key, str) or not key:
            raise TableError("主键列名必须是非空字符串")
        self.name = name
        self.key = key
        self._rows = {}

    def key_of(self, row):
        """取一行的主键值；缺列或为空都算坏行。"""
        if not isinstance(row, dict):
            raise TableError("%s: 行必须是 dict，收到 %r" % (self.name, row))
        if self.key not in row:
            raise TableError("%s: 行里没有主键列 %s" % (self.name, self.key))
        value = row[self.key]
        if value is None:
            raise TableError("%s: 主键 %s 不能为空" % (self.name, self.key))
        return value

    def get(self, key):
        """按主键取一行的副本，没有就返回 None。"""
        row = self._rows.get(key)
        return None if row is None else dict(row)

    def rows(self):
        """当前所有行的副本，按主键首次落库的顺序。"""
        return [dict(row) for row in self._rows.values()]

    def __len__(self):
        return len(self._rows)

    def __contains__(self, key):
        return key in self._rows

    def _put(self, row):
        self._rows[self.key_of(row)] = dict(row)

    def _drop(self, key):
        del self._rows[key]


class Dataset:
    """一组内存表，按变更流更新。"""

    def __init__(self, *tables):
        self._tables = {}
        for table in tables:
            if table.name in self._tables:
                raise TableError("表名重复: %r" % (table.name,))
            self._tables[table.name] = table

    def table(self, name):
        try:
            return self._tables[name]
        except KeyError:
            raise TableError("没有这张表: %r" % (name,))

    def apply(self, change):
        """把一条变更落进对应的表，返回受影响行的主键。

        对不上的变更一律抛 TableError：表不存在、重复插入、更新或删除一个
        不存在的行、before 与当前内容不一致、字段该带没带或不该带带了。
        """
        if not isinstance(change, dict):
            raise TableError("变更必须是 dict")
        seq = change.get("seq")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq <= 0:
            raise TableError("seq 必须是正整数，收到 %r" % (seq,))
        op = change.get("op")
        if op not in OPS:
            raise TableError("未知操作类型 %r" % (op,))
        table = self.table(change.get("table"))
        before = change.get("before")
        after = change.get("after")
        if op == "insert":
            if after is None or before is not None:
                raise TableError("insert 只带 after")
            key = table.key_of(after)
            if key in table:
                raise TableError("%s: 重复插入 %r" % (table.name, key))
            table._put(after)
        elif op == "update":
            if before is None or after is None:
                raise TableError("update 必须同时带 before 和 after")
            key = table.key_of(after)
            if table.key_of(before) != key:
                raise TableError("update 不能改主键")
            current = table.get(key)
            if current is None:
                raise TableError("%s: 更新不存在的行 %r" % (table.name, key))
            if current != before:
                raise TableError("%s: before 与当前行不一致: %r" % (table.name, key))
            table._put(after)
        else:
            if before is None or after is not None:
                raise TableError("delete 只带 before")
            key = table.key_of(before)
            current = table.get(key)
            if current is None:
                raise TableError("%s: 删除不存在的行 %r" % (table.name, key))
            if current != before:
                raise TableError("%s: before 与当前行不一致: %r" % (table.name, key))
            table._drop(key)
        return key

    def __repr__(self):
        return "Dataset(%s)" % ", ".join(
            "%s=%d" % (name, len(table)) for name, table in self._tables.items())


def insert_change(seq, table, row):
    """造一条插入变更。"""
    return {"seq": seq, "table": table, "op": "insert", "before": None,
            "after": dict(row)}


def update_change(seq, table, before, after):
    """造一条更新变更，before 是旧行，after 是新行。"""
    return {"seq": seq, "table": table, "op": "update",
            "before": dict(before), "after": dict(after)}


def delete_change(seq, table, row):
    """造一条删除变更，row 是被删掉的那行。"""
    return {"seq": seq, "table": table, "op": "delete", "before": dict(row),
            "after": None}


class ChangeLog:
    """攒一条按顺序的变更流，seq 从 start 起自增。"""

    def __init__(self, start=1):
        if not isinstance(start, int) or start <= 0:
            raise TableError("起点 seq 必须是正整数")
        self._next = start
        self._changes = []

    @property
    def next_seq(self):
        """下一条变更会拿到的 seq。"""
        return self._next

    def _take(self):
        seq = self._next
        self._next += 1
        return seq

    def insert(self, table, row):
        change = insert_change(self._take(), table, row)
        self._changes.append(change)
        return change

    def update(self, table, before, after):
        change = update_change(self._take(), table, before, after)
        self._changes.append(change)
        return change

    def delete(self, table, row):
        change = delete_change(self._take(), table, row)
        self._changes.append(change)
        return change

    def changes(self):
        """到目前为止的变更，按 seq 顺序，连行一起拷贝。"""
        copies = []
        for change in self._changes:
            copy = dict(change)
            for side in ("before", "after"):
                if change[side] is not None:
                    copy[side] = dict(change[side])
            copies.append(copy)
        return copies

    def __len__(self):
        return len(self._changes)
