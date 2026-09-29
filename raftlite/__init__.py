"""raftlite：一个纯标准库的单机复制日志。

当前对外能力是 Log：一边追加一边读任期，末尾可截断，带一个已经列到哪儿的
标记。多节点复制模拟、多数提交与应用、任期与选举、冲突回退与覆盖都留待
在这个基础上补齐。
"""

from .errors import InvalidIndex, RaftError, UnknownNode
from .log import Entry, Log

__all__ = [
    "Entry",
    "InvalidIndex",
    "Log",
    "RaftError",
    "UnknownNode",
]