"""profiledp: 纯标准库的网格铺放计数工具包（当前为改造前基线）。

导出 ProfileDp 与全部异常类型。
"""

from .profile import (
    ProfileDp,
    Erro,
    SizeErro,
    GridErro,
    WeightErro,
    ShapeErro,
    MAX_MASK_BITS,
)

__all__ = [
    "ProfileDp",
    "Erro",
    "SizeErro",
    "GridErro",
    "WeightErro",
    "ShapeErro",
    "MAX_MASK_BITS",
]
