"""triex: 朴素异或集合工具。

当前对外提供唯一的类 FlatXor, 所有查询都在一个整数列表上线性扫描。
改造目标是以二进制字典树为核心的异或最值工具集, 详见 README。
"""

from .bits import FlatXor

__all__ = ["FlatXor"]
