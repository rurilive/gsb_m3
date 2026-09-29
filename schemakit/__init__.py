"""schemakit：一个纯标准库的记录模式迁移器。

当前对外能力是 migrate：按固定规则把一条记录改到 v1 格式。带依赖排序、
可回滚、可组合的迁移链与声明式字段校验都留待在这个基础上补齐。
"""

from .errors import (
    BranchError,
    CycleError,
    MigrationError,
    SchemaKitError,
    UnknownVersionError,
    ValidationError,
    VersionGapError,
)
from .migrate import VERSION_KEY, migrate

__all__ = [
    "BranchError",
    "CycleError",
    "MigrationError",
    "SchemaKitError",
    "UnknownVersionError",
    "VERSION_KEY",
    "ValidationError",
    "VersionGapError",
    "migrate",
]
