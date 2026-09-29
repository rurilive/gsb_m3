"""bitlib：位集合工具包，纯标准库，无外部依赖。

当前只提供最朴素的 BoolBits：位集合用一个布尔列表存，置位与清零直接改
列表里的某一格，两个集合求与或需要逐位循环。没有字级存储、没有位运算，
也没有集合运算的加速。
"""

from .bitset import BitlibError, BoolBits

__all__ = ["BitlibError", "BoolBits"]
