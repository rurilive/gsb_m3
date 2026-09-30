"""rangeq: 一个可变序列上的朴素区间操作工具。

当前只有平铺列表实现，见 rangeq/seq.py。区间加、区间求和、区间最值
都把整段逐个重扫一遍，单点查询直接读数组，规模一大就慢。分块（根号
分治）改造见任务描述。
"""

from rangeq.seq import (
    RangeqError,
    EmptyRangeError,
    IndexOutOfRangeError,
    Query,
)

__all__ = [
    "Query",
    "RangeqError",
    "EmptyRangeError",
    "IndexOutOfRangeError",
]
