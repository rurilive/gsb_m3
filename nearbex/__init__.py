"""nearbex: 一个极简的文本相似度工具包。

当前版本只提供最朴素的逐字符比较能力。
"""

from .sim import CharDiff

__all__ = ["CharDiff"]
