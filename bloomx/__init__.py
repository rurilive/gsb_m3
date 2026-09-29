"""bloomx：成员集合工具包（纯标准库）。

当前只导出基线类 ExactSet，精确成员集合。
"""

from .member import ExactSet

__all__ = ["ExactSet"]
