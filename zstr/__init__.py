"""zstr: 字符串前后缀工具的朴素实现。

当前只有逐位直接比较这一条路：Z 数组按每个位置从头比较，
出现位置按每个起点逐位对齐，整周期与最小周期靠逐位试。
见 zstr/naive.py，线性做法见任务描述。
"""

from zstr.naive import (
    Erro,
    TextError,
    TextTools,
    min_period,
    occurrences,
    z_array,
)

__all__ = ["Erro", "TextError", "TextTools", "min_period", "occurrences", "z_array"]
