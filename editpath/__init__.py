"""editpath: 编辑距离与序列对齐工具。

当前只提供一份朴素实现 EditPath，编辑距离靠逐步枚举三种操作递归展开，
最长公共子序列与最长公共子串靠枚举子序列与子串，是升级为二维动态规划
之前的基线。纯标准库，无外部依赖。
"""

from editpath.core import EditPath, EditPathError, TypeMismatchError

__all__ = ["EditPath", "EditPathError", "TypeMismatchError"]
