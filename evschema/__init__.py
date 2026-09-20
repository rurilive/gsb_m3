"""evschema: 审计事件存储，事件按 schema 版本校验后落盘。"""

from .evolution import EdgePlan, build_edge, check_compatibility
from .registry import SchemaRegistry
from .schema import ORDER_V1, Schema, SchemaError, type_ok
from .store import EventStore

__all__ = [
    "EdgePlan",
    "EventStore",
    "ORDER_V1",
    "Schema",
    "SchemaError",
    "SchemaRegistry",
    "build_edge",
    "check_compatibility",
    "type_ok",
]
