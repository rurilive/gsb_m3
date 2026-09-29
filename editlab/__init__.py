"""editlab: 字符串差异工具。

当前只提供基于逐位比较的 HammDiff，作为编辑距离改造前的基线。
"""

from editlab.diff import EditError, HammDiff, LengthMismatchError

__all__ = ["EditError", "HammDiff", "LengthMismatchError"]
