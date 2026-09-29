"""colstore: 内存里的列式压缩存储。

当前只有一列整数原样存放的朴素实现，见 colstore/column.py。
多种列编码、惰性解码、按需扫描与谓词下推见任务描述。
"""

from colstore.column import Column
from colstore.store import Store

__all__ = ["Column", "Store"]
