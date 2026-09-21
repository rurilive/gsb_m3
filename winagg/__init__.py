"""winagg: 规则引擎的进程内事件指标聚合。

按事件时间累计计数，时钟从外部注入，纯标准库。
"""

from winagg.sliding import ClosedWindow, MultiWindowCounter, WindowedCounter
from winagg.window import EventCounter

__all__ = ["ClosedWindow", "EventCounter", "MultiWindowCounter",
           "WindowedCounter"]
