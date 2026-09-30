"""gtheor: 纯标准库的公平组合游戏有向图局面工具包（当前为改造前基线）。

导出 GameKit 与全部异常类型。
"""

from .graph import (
    GameKit,
    GameErro,
    GraphErro,
    StateErro,
)

__all__ = [
    "GameKit",
    "GameErro",
    "GraphErro",
    "StateErro",
]
