"""orderstat: 一个朴素的无序序列次序统计工具。

当前只有平铺列表实现，见 orderstat/seq.py。第几个最小、前几个最小之和
以及中位数都把整段复制排序一遍再取，规模一大、查询一多就反复全排序。
快速选择与堆维护的改造见任务描述。
"""

from orderstat.seq import (
    EmptySequenceError,
    OrderStatError,
    RankOutOfRangeError,
    Selector,
)

__all__ = [
    "Selector",
    "OrderStatError",
    "RankOutOfRangeError",
    "EmptySequenceError",
]
