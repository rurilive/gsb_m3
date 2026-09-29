"""autocmplt: 内存里的朴素前缀补全。

当前只有逐词扫前缀的实现，见 autocmplt/scan.py。
字典树检索、热度排序、Top-K 截断、增量学习、模糊补全与序列化
见任务描述。
"""

from autocmplt.scan import Autocomplete

__all__ = ["Autocomplete"]
