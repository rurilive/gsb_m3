"""mcfx: 纯标准库的网络流工具包（当前为改造前基线）。

导出 FlatMcf 与 McfError。
"""

from .flow import FlatMcf, McfError

__all__ = ["FlatMcf", "McfError"]
