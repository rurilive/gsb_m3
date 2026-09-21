"""字段二级索引。

基线实现：内存里放一份值到主键集合的映射，每次查询前都把主数据
从头全量扫一遍现算，写完即弃，不做任何增量维护。
"""


class SecondaryIndex:
    """按记录里某个字段的字符串值找主键。

    记录里该字段缺失、或者取到的不是字符串，这条记录就不进索引。
    """

    def __init__(self, store, field):
        self.store = store
        self.field = field
        self._buckets = {}
        self._rebuilds = 0
        self._lookups = 0
        self._records_scanned = 0

    def rebuild(self):
        """从主数据全量重建，返回索引到的条目数（值与主键的挂载总数）。"""
        buckets = {}
        scanned = 0
        for key, record in self.store.scan():
            scanned += 1
            value = self._value_of(record)
            if value is None:
                continue
            buckets.setdefault(value, set()).add(key)
        self._buckets = buckets
        self._rebuilds += 1
        self._records_scanned += scanned
        return self._entry_count()

    def lookup(self, value):
        """查一个值下面的全部主键，排序返回，没有则空列表。

        基线每次调用都先全量重建再查。
        """
        self.rebuild()
        self._lookups += 1
        return sorted(self._buckets.get(value, ()))

    def values(self):
        """全部索引值，排序列表。"""
        self.rebuild()
        return sorted(self._buckets)

    def stats(self):
        """计数快照，返回独立 dict。"""
        return {
            "rebuilds": self._rebuilds,
            "lookups": self._lookups,
            "records_scanned": self._records_scanned,
            "entries": self._entry_count(),
        }

    # 内部

    def _value_of(self, record):
        value = record.get(self.field)
        return value if isinstance(value, str) else None

    def _entry_count(self):
        return sum(len(bucket) for bucket in self._buckets.values())
