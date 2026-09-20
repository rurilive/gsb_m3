"""mvjoin: 内存表的变更流与视图。

数据集按变更流更新；FullView 全量重算分组聚合，支持单表过滤与两表等值连接。
"""

from mvjoin.full import FullView, merge_row
from mvjoin.spec import AGGS, Join, SpecError, ViewSpec
from mvjoin.tables import (
    OPS,
    ChangeLog,
    Dataset,
    Table,
    TableError,
    delete_change,
    insert_change,
    update_change,
)

__all__ = [
    "ChangeLog",
    "Dataset",
    "FullView",
    "Join",
    "SpecError",
    "Table",
    "TableError",
    "ViewSpec",
    "delete_change",
    "insert_change",
    "merge_row",
    "update_change",
]
