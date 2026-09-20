"""全量重算的视图引擎。

FullView 每次 recompute 都从头来：右表按连接键建一次索引，左表逐行配对，
再过滤、分组、聚合。任何变更落库后重算一次，就得到最新结果。
"""

from mvjoin.spec import ViewSpec


def merge_row(join, left_row, right_row):
    """把两个表的行拼成一行，键带表名前缀。"""
    merged = {}
    for column, value in left_row.items():
        merged["%s.%s" % (join.left, column)] = value
    for column, value in right_row.items():
        merged["%s.%s" % (join.right, column)] = value
    return merged


class FullView:
    """全量重算的视图。"""

    def __init__(self, spec):
        if not isinstance(spec, ViewSpec):
            raise TypeError("spec 必须是 ViewSpec")
        self.spec = spec
        self.refreshes = 0
        self.last_pairs = 0
        self._result = {}

    def pairs(self, dataset):
        """把所有配对过一遍：单表视图就是逐行，连接视图按连接键配对。

        连接键为 None 的行跳过，谁也不配；右表同键多行时左表逐行配过去。
        """
        spec = self.spec
        if spec.join is None:
            for row in dataset.table(spec.table).rows():
                yield row, None
            return
        buckets = {}
        for row in dataset.table(spec.join.right).rows():
            value = row.get(spec.join.right_key)
            if value is None:
                continue
            buckets.setdefault(value, []).append(row)
        for row in dataset.table(spec.join.left).rows():
            value = row.get(spec.join.left_key)
            if value is None:
                continue
            for other in buckets.get(value, ()):
                yield row, other

    def recompute(self, dataset):
        """从头算一遍，记下结果并返回它。"""
        spec = self.spec
        result = {}
        pairs = 0
        for left_row, right_row in self.pairs(dataset):
            pairs += 1
            merged = left_row if right_row is None else merge_row(
                spec.join, left_row, right_row)
            if spec.where is not None and not spec.where(merged):
                continue
            group = merged.get(spec.group)
            bucket = result.get(group)
            if bucket is None:
                bucket = result[group] = {name: 0 for name, _, _ in spec.metrics}
            for name, agg, column in spec.metrics:
                if agg == "count":
                    bucket[name] += 1
                else:
                    bucket[name] += merged[column]
        self.refreshes += 1
        self.last_pairs = pairs
        self._result = result
        return self.result()

    def result(self):
        """最近一次重算的结果副本，没算过就是空 dict。"""
        return {group: dict(values) for group, values in self._result.items()}

    def __repr__(self):
        return "FullView(%r, refreshes=%d)" % (self.spec.name, self.refreshes)
