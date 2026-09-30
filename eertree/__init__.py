"""eertree: 朴素回文子串工具。

当前只有枚举子串当场判断的实现，见 eertree/tree.py。判断某子串是否回文
用双指针镜像比对，枚举全部回文子串把所有下标区间过一遍再挑，统计某位置
为结尾的回文个数与个数、以某位置结尾的最长回文长度、判断某个回文是否出
现，也都靠现算，代价随文本长度平方增长。

回文自动机（回文树，失配链加长度零与长度负一两个根）、本质不同回文统计、
逐位置增量、各回文出现次数、最长回文后缀、按长度分布见任务描述。
"""

from eertree.tree import (
    BrutePalTree,
    Erro,
    IllegalArgument,
    IndexOutOfRange,
    NotASubstring,
)

__all__ = [
    "BrutePalTree",
    "Erro",
    "IllegalArgument",
    "IndexOutOfRange",
    "NotASubstring",
]
