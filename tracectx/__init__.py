"""tracectx: 批处理里的跨线程执行小工具。"""

from tracectx.batch import ItemFailure, first_failure, map_batch
from tracectx.detached import async_call, run_detached
from tracectx.gate import Gate
from tracectx.trace import (
    TracedThread,
    TracedThreadPoolExecutor,
    current_correlation_id,
    format_report,
    get_slow_threshold,
    print_report,
    set_slow_threshold,
    span,
    start_trace,
)

__all__ = [
    "Gate",
    "ItemFailure",
    "TracedThread",
    "TracedThreadPoolExecutor",
    "async_call",
    "current_correlation_id",
    "first_failure",
    "format_report",
    "get_slow_threshold",
    "map_batch",
    "print_report",
    "run_detached",
    "set_slow_threshold",
    "span",
    "start_trace",
]
