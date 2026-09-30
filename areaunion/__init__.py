"""areaunion: 纯标准库的轴对齐矩形集合工具包（当前为改造前基线）。

导出 RectSet 与全部异常类型。
"""

from .area import (
    RectSet,
    Erro,
    RectErro,
    CountErro,
    IndexErro,
)

__all__ = [
    "RectSet",
    "Erro",
    "RectErro",
    "CountErro",
    "IndexErro",
]
