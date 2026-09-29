"""schemakit 迁移内核。

当前对外能力只有一个朴素函数 migrate：按固定规则把一条记录改到 v1 格式。
可组合、可回滚、带依赖排序的迁移链留待在这个基础上补齐。

迁移链要支持：每个迁移声明 from_version 与 to_version 及 up 变换，多条迁移
按版本序串成链；apply 前向迁移、revert 反向迁移且 up/down 互逆；对一批记录
顺序执行整条链，失败时整批回滚或标记失败；幂等与未知版本 fail fast。
"""

from .errors import MigrationError

VERSION_KEY = "version"


def migrate(record):
    """把一条记录按固定规则改到 v1 格式，返回新字典。

    规则固定：nickname 重命名为 name（两者同时存在时 nickname 胜出）、
    缺失 name 时补空串、version 一律置 1。入参记录不被改写。
    """
    if not isinstance(record, dict):
        raise MigrationError("记录必须是字典: %r" % (record,))
    out = dict(record)
    if "nickname" in out:
        out["name"] = out.pop("nickname")
    out.setdefault("name", "")
    out[VERSION_KEY] = 1
    return out
