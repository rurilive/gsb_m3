"""slopeopt: 纯标准库的斜率型动态规划最优化工具包（当前为改造前基线）。

导出 OptKit、Program 与全部异常类型。
"""

from .core import (
    OptErro,
    OptKit,
    Program,
    ProgramErro,
    SequenceErro,
)

__all__ = [
    "OptErro",
    "OptKit",
    "Program",
    "ProgramErro",
    "SequenceErro",
]
