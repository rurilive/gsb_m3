"""stampkit：报表服务使用的时间戳工具库。

秒/毫秒换算、按固定间隔的桶对齐、时间跨度计算与归档打包。
只依赖 Python 标准库。
"""

from .align import align_many, bucket_index, bucket_span, ceil_bucket, floor_bucket
from .span import duration_between, format_duration, pack_duration, unpack_duration
from .units import MS_PER_SECOND, guess_unit, to_millis, to_seconds

__version__ = "0.4.2"

__all__ = [
    "MS_PER_SECOND",
    "align_many",
    "bucket_index",
    "bucket_span",
    "ceil_bucket",
    "duration_between",
    "floor_bucket",
    "format_duration",
    "guess_unit",
    "pack_duration",
    "to_millis",
    "to_seconds",
    "unpack_duration",
]
