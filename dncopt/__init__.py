"""dncopt：分段最优划分的基线包（改造前）。

公开朴素实现与异常基类。
"""

from .core import (
    DncoptErro,
    InputErro,
    Optimizer,
)

__all__ = [
    "DncoptErro",
    "InputErro",
    "Optimizer",
]
