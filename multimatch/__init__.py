"""multimatch: 一个极简的多模式匹配包。

目前只导出现有的朴素逐模式扫描匹配器。
"""

from multimatch.find import EachPattern, InvalidPatternError, Match, MultiMatchError

__all__ = ["EachPattern", "InvalidPatternError", "Match", "MultiMatchError"]
