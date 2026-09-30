"""beatsx：可变序列的区间操作工具包（当前为改造前的朴素基线）。

导出 BeatsSeq 类与全部异常类型。基线只用一个普通列表存数据，区间取
最小值、区间加、区间赋值、区间求和与区间最值统统逐元素扫过整段。
"""

from .segment import (
    BadRangeError,
    BadValueError,
    BeatsSeq,
    EmptySeqError,
    SegmentError,
)

__all__ = [
    "BadRangeError",
    "BadValueError",
    "BeatsSeq",
    "EmptySeqError",
    "SegmentError",
]
