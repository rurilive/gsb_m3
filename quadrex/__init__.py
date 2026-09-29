"""quadrex: 纯标准库的点集空间查询。

当前只提供最朴素的空间查询实现：把点存在列表里，按矩形查询时逐个点判断
是否落在范围内，没有树、没有划分、没有层次。
"""

from quadrex.points import LinearPoints

__all__ = ["LinearPoints"]
