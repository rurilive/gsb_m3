"""视图规格。

单表视图的列名不带前缀，连接视图的列名带表名前缀：

    ViewSpec(name="paid_by_region", table="orders", where=..., group="region",
             metrics=[("cnt", "count", None), ("amount", "sum", "amount")])
    ViewSpec(name="category_orders", join=Join("orders", "skus", "sku", "sku"),
             group="skus.category",
             metrics=[("cnt", "count", None), ("amount", "sum", "orders.amount")])

where 拿到的是一行：单表视图是原行，连接视图是两表字段拼起来的 dict，
键形如 "orders.sku"。连接键为 None 的行配不上任何东西，结果里不会有它们。
"""

AGGS = ("count", "sum")


class SpecError(ValueError):
    """规格写错了。"""


class Join:
    """等值连接：left 表的 left_key 连 right 表的 right_key。"""

    __slots__ = ("left", "right", "left_key", "right_key")

    def __init__(self, left, right, left_key, right_key):
        for value, what in ((left, "left"), (right, "right"),
                            (left_key, "left_key"), (right_key, "right_key")):
            if not isinstance(value, str) or not value:
                raise SpecError("%s 必须是非空字符串" % (what,))
        if left == right:
            raise SpecError("连接两边不能是同一张表")
        self.left = left
        self.right = right
        self.left_key = left_key
        self.right_key = right_key


class ViewSpec:
    """一张视图的规格：数据从哪来、按什么分组、聚什么。"""

    __slots__ = ("name", "table", "join", "where", "group", "metrics")

    def __init__(self, name, group, metrics, table=None, join=None, where=None):
        if not isinstance(name, str) or not name:
            raise SpecError("视图名必须是非空字符串")
        if (table is None) == (join is None):
            raise SpecError("table 和 join 必须二选一")
        if table is not None and (not isinstance(table, str) or not table):
            raise SpecError("表名必须是非空字符串")
        if join is not None and not isinstance(join, Join):
            raise SpecError("join 必须是 Join")
        if where is not None and not callable(where):
            raise SpecError("where 必须是可调用对象")
        if not isinstance(group, str) or not group:
            raise SpecError("group 必须是非空字符串")
        self.name = name
        self.table = table
        self.join = join
        self.where = where
        self.group = self._column(group, "group")
        self.metrics = self._metrics(metrics)

    def _column(self, ref, what):
        """校验一个列引用，返回它的规范写法。"""
        if not isinstance(ref, str) or not ref:
            raise SpecError("%s 必须是字符串列名" % (what,))
        if self.join is None:
            if "." in ref:
                raise SpecError("%s: 单表视图的列名不带前缀: %r" % (what, ref))
            return ref
        side, dot, column = ref.partition(".")
        if not dot or not column or side not in (self.join.left, self.join.right):
            raise SpecError("%s: 连接视图的列名要写成 表名.列名: %r" % (what, ref))
        return ref

    def _metrics(self, metrics):
        if isinstance(metrics, str) or not metrics:
            raise SpecError("至少要有一个聚合指标")
        out = []
        seen = set()
        for item in metrics:
            if not isinstance(item, tuple) or len(item) != 3:
                raise SpecError("指标要写成 (名字, 聚合, 列) 三元组: %r" % (item,))
            name, agg, column = item
            if not isinstance(name, str) or not name:
                raise SpecError("指标名字必须是非空字符串")
            if name in seen:
                raise SpecError("指标名字重复: %r" % (name,))
            seen.add(name)
            if agg not in AGGS:
                raise SpecError("未知聚合 %r" % (agg,))
            if agg == "count":
                if column is not None:
                    raise SpecError("count 不带列")
            else:
                self._column(column, "sum 的列")
            out.append((name, agg, column))
        return tuple(out)

    def sources(self):
        """这张视图依赖的表名。"""
        if self.join is None:
            return (self.table,)
        return (self.join.left, self.join.right)

    def __repr__(self):
        return "ViewSpec(%r, group=%r, metrics=%r)" % (self.name, self.group,
                                                       self.metrics)
