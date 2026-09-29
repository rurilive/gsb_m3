"""timectl: 一个朴素的定时器调度器。

当前只提供同步循环触发的 LoopTimer：每次到点都直接同步调用回调，没有
延迟、周期、防抖与节流的区分，也没有统一的时钟驱动接口。
"""

from timectl.timer import LoopTimer, LoopHandle

__all__ = ["LoopTimer", "LoopHandle"]