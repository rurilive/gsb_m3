"""bitmaskx: 纯标准库的集合状压工具包（当前为改造前基线）。

导出 MaskDp 与全部异常类型。
"""

from .bitmask import (
    MaskDp,
    Erro,
    SizeErro,
    GraphErro,
    WeightErro,
    CoverErro,
)

__all__ = [
    "MaskDp",
    "Erro",
    "SizeErro",
    "GraphErro",
    "WeightErro",
    "CoverErro",
]
