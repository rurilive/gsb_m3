"""qsketch：埋点链路的延迟统计库。

SampleSet 全量留样本，查询时排序取分位；ShardSet 按分片记账，
查询时把各片的样本拼起来算；codec 负责落盘与读回。
"""

from qsketch import codec
from qsketch.errors import EmptySetError, FormatError, SketchError
from qsketch.samples import SampleSet, check_quantile, quantile_of_sorted
from qsketch.shards import ShardSet

__all__ = [
    "SampleSet",
    "ShardSet",
    "codec",
    "SketchError",
    "EmptySetError",
    "FormatError",
    "quantile_of_sorted",
    "check_quantile",
]
