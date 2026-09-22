"""分片记账。

每个分片单独攒样本，查询时把各片的样本拼起来算精确分位。
分片名按 str 处理，跨片重复的样本不去重。
"""

from qsketch.errors import EmptySetError, SketchError
from qsketch.samples import SampleSet, quantile_of_sorted


class ShardSet:
    """按分片攒样本的集合，单线程使用。"""

    def __init__(self):
        self._shards = {}

    def add(self, shard, value):
        """给分片收一条样本，分片不存在就建。分片名必须是 str。"""
        if not isinstance(shard, str):
            raise SketchError("shard name must be a str, got %r" % (shard,))
        sample_set = self._shards.get(shard)
        if sample_set is None:
            sample_set = self._shards[shard] = SampleSet()
        return sample_set.add(value)

    def names(self):
        """排好序的分片名。"""
        return sorted(self._shards)

    def count(self, shard=None):
        """给分片名数该片，不给就数全部。"""
        if shard is None:
            return sum(s.count() for s in self._shards.values())
        return self._shard(shard).count()

    def values(self, shard=None):
        """样本副本：给分片名给该片的，不给就按分片名顺序拼起来。"""
        if shard is None:
            merged = []
            for name in self.names():
                merged.extend(self._shards[name].values())
            return merged
        return self._shard(shard).values()

    def quantile(self, q):
        """跨分片的精确分位：所有样本一起排序。"""
        values = self.values()
        if not values:
            raise EmptySetError("quantile of empty shard set")
        values.sort()
        return quantile_of_sorted(values, q)

    def merge(self, other):
        """并进另一个 ShardSet，同名片按本片在前拼接。

        返回新对象，两边都不动。分片名必须两边都是 str
        （add 已经卡过），这里不再重复校验。
        """
        if not isinstance(other, ShardSet):
            raise SketchError(
                "merge expects a ShardSet, got %s" % type(other).__name__)
        merged = ShardSet()
        for name in sorted(set(self._shards) | set(other._shards)):
            values = self._values_of(name) + other._values_of(name)
            merged._shards[name] = SampleSet(values)
        return merged

    # ---- 内部 ----

    def _shard(self, name):
        sample_set = self._shards.get(name)
        if sample_set is None:
            raise SketchError("unknown shard: %r" % (name,))
        return sample_set

    def _values_of(self, name):
        sample_set = self._shards.get(name)
        return sample_set.values() if sample_set is not None else []
