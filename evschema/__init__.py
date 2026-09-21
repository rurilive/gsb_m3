"""evschema: 审计事件存储，事件按 schema 版本校验后落盘。"""

from .evolve import StepPlan, check_compatibility
from .registry import SchemaRegistry
from .schema import ORDER_V1, ORDER_V2, ORDER_V3, Schema, SchemaError, type_ok
from .store import EventStore

__all__ = [
    "EventStore",
    "ORDER_V1",
    "ORDER_V2",
    "ORDER_V3",
    "Schema",
    "SchemaError",
    "SchemaRegistry",
    "StepPlan",
    "check_compatibility",
    "type_ok",
]
