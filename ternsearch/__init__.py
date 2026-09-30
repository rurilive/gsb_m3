"""ternsearch: 离散点上的朴素极值工具。

现状只有一条路径：把定义域里的每个整数点或每条离散数据逐个算一遍函数值，
从头扫到尾再挑出极值，见 ternsearch/extremum.py。
三分法收窄、导数或差分加二分、斐波那契搜索或黄金分割比、单峰判定与求值
次数对照见任务描述。
"""

from ternsearch.extremum import ExtremumError, PeakFinder, UnimodalError

__all__ = ["ExtremumError", "UnimodalError", "PeakFinder"]
