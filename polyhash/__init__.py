"""polyhash: 多项式哈希字符串池。

当前只提供一份只走逐字符比较的 StringPool，作为滚动哈希改造前的基线。
"""

from polyhash.core import PolyHashError, StringPool, build_text

__all__ = ["PolyHashError", "StringPool", "build_text"]
