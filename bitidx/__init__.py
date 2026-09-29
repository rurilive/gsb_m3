"""bitidx: 内存里的朴素表与全量布尔扫描。

当前只有逐行判条件的扫描实现，见 bitidx/recordset.py。
位图索引、位运算查询、压缩位图、计数分页与排序键见任务描述。
"""

from bitidx.recordset import RecordSet

__all__ = ["RecordSet"]
