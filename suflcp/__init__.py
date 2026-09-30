"""suflcp: 纳秒级后缀数组与最长公共前缀的朴素雏形。

当前只有最直白的两条路：把文本的所有后缀取出来逐个字典序排序得到
后缀数组，相邻后缀的最长公共前缀则逐字符现算。规模一大就慢，但没有
任何索引结构，也没有任意两个后缀之间的查询。倍增建后缀数组、用排名
做键的基数排序、卡萨伊相邻最长公共前缀线性扫描、区间最小值与稀疏表
支撑的任意两后缀查询，以及与之对拍的独立做法见任务描述。
"""

from suflcp.engine import (
    Erro,
    SuffixError,
    SuffixArray,
    common_prefix_len,
    naive_lcp_array,
    naive_suffix_array,
)

__all__ = [
    "Erro",
    "SuffixError",
    "SuffixArray",
    "common_prefix_len",
    "naive_lcp_array",
    "naive_suffix_array",
]
