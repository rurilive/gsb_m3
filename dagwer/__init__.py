"""dagwer: 一个极简的有向无环图校验包。

当前版本只提供最朴素的成环检查能力。
"""

from .check import DagCheck

__all__ = ["DagCheck"]
