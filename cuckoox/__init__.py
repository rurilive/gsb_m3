"""cuckoox：成员集合工具包（纯标准库）。

当前只导出基线类 ExactBag，用精确集合实现。
"""

from .set import ExactBag

__all__ = ["ExactBag"]
