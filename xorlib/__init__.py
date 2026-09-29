"""xorlib: 朴素异或集合工具。

当前对外提供唯一的类 FlatXor, 所有查询都在一个整数列表上线性扫描。
"""

from .xor import FlatXor

__all__ = ["FlatXor"]
