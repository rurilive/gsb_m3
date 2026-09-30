"""blockx: 一个可变序列上的朴素区间操作工具。

当前只有平铺列表实现，见 blockx/seq.py。区间求和、区间加、区间最值
都把整段重扫一遍，单点查询直接按下标取，规模一大就慢。分块（根号
分治）改造见任务描述。
"""

from blockx.seq import (
    BlockxError,
    EmptySequenceError,
    IndexOutOfRangeError,
    Seq,
)

__all__ = [
    "Seq",
    "BlockxError",
    "EmptySequenceError",
    "IndexOutOfRangeError",
]
