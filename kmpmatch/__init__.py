"""kmpmatch: 字符串匹配工具的朴素实现。

当前只有逐位直接比较这一条路：出现位置按每个起点逐位对齐，最长公共
前后缀长度数组按每个候选长度重算，整周期与最小周期靠逐位试，多模式
匹配逐个模式各扫一遍。见 kmpmatch/naive.py，线性做法见任务描述。
"""

from kmpmatch.naive import (
    Erro,
    TextError,
    TextTools,
    count,
    is_periodic,
    min_period,
    occurrences,
    occurrences_many,
    prefix_naive,
)

__all__ = [
    "Erro",
    "TextError",
    "TextTools",
    "count",
    "is_periodic",
    "min_period",
    "occurrences",
    "occurrences_many",
    "prefix_naive",
]
