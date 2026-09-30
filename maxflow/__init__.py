"""maxflow：网络最大流与最小割，纯标准库，无外部依赖。

当前对外能力是一份朴素实现：在残量网络上反复做一次深度搜索或广度搜索
找一条增广路，沿路逐条推流，直到再也找不到增广路；最小割则靠枚举割集
或按可达性直接读出。分层推进的阻塞流、增广次数与分层轮数的差距统计、
以及更完整的边界覆盖都留待在这个基础上补齐。
"""

from .flow import (
    Edge,
    FlowError,
    FlowNetwork,
    FlowResult,
    InvalidCapacityError,
    MinCutResult,
    NoPathError,
    NodeNotFoundError,
    SelfLoopError,
    SourceSinkError,
    min_cut,
    max_flow,
)

__all__ = [
    "Edge",
    "FlowError",
    "FlowNetwork",
    "FlowResult",
    "InvalidCapacityError",
    "MinCutResult",
    "NoPathError",
    "NodeNotFoundError",
    "SelfLoopError",
    "SourceSinkError",
    "max_flow",
    "min_cut",
]
