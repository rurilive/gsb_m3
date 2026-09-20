"""tickbase：压测工具里用的进程内任务调度器。

对外导出：
- Scheduler / Task：调度器与任务对象
- IntervalTrigger / DailyTrigger：按间隔、按每日时刻
- Clock / SystemClock / ManualClock：注入式时间源
- InlineExecutor：默认的当场执行器
"""

from .clock import Clock, ManualClock, SystemClock
from .executor import InlineExecutor
from .scheduler import Scheduler, Task
from .triggers import DailyTrigger, IntervalTrigger

__all__ = [
    "Clock",
    "ManualClock",
    "SystemClock",
    "InlineExecutor",
    "Scheduler",
    "Task",
    "DailyTrigger",
    "IntervalTrigger",
]
