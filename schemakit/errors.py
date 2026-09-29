"""schemakit 自有异常类型。

迁移器在定义、排序与执行过程中出现的可诊断错误都在这里定义，全部继承
SchemaKitError，调用方只捕捉 SchemaKitError 即可一次性接住所有错误。
"""


class SchemaKitError(Exception):
    """迁移器所有可诊断错误的基类。"""


class MigrationError(SchemaKitError):
    """迁移定义或执行期错误：迁移非法、链不可执行等。"""


class UnknownVersionError(MigrationError):
    """未知版本：记录当前的版本或查询的目标版本不在迁移图里。"""


class VersionGapError(MigrationError):
    """版本链缺口：两个版本之间缺少能把它们串起来的迁移。"""


class CycleError(MigrationError):
    """迁移图存在循环依赖，无法排出唯一执行顺序。"""


class BranchError(MigrationError):
    """两个版本之间存在多条迁移路径，去向不唯一。"""


class ValidationError(SchemaKitError):
    """字段校验失败：必填字段缺失或字段类型不符。"""
