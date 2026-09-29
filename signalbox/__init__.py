"""signalbox：一个纯标准库的反应式信号库。

当前对外能力只有 Observable 这一个朴素可观察值：存一个值，设值时把新值同步
通知给订阅者。依赖图、惰性求值、批处理与副作用调度都留待在这个基础上补齐。
"""

from .observable import Observable

__all__ = ["Observable"]