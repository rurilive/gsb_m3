"""graycode: 格雷码与子集枚举的朴素实现。

当前只有反复试凑这一条路：生成格雷码序列靠试探候选串加深搜回退，判断合法
性、定位某个串都靠把整条序列造出来再逐个比对，子集枚举按二进制计数顺序。
见 graycode.naive，线性做法见任务描述。
"""

from graycode.naive import (
    Erro,
    GrayError,
    GrayTools,
    diff_count,
    gray_index,
    gray_sequence,
    is_gray_sequence,
    subsets_in_bit_order,
    subsets_in_gray_order,
)

__all__ = [
    "Erro",
    "GrayError",
    "GrayTools",
    "diff_count",
    "gray_index",
    "gray_sequence",
    "is_gray_sequence",
    "subsets_in_bit_order",
    "subsets_in_gray_order",
]
