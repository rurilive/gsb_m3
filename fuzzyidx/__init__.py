"""fuzzyidx: 模糊检索倒排索引。

当前只提供一份只支持精确整词匹配的 FuzzyIndex，作为模糊检索改造前的基线。
"""

from fuzzyidx.index import FuzzyIndex

__all__ = ["FuzzyIndex"]