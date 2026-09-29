"""lockfolio: 进程内分布式锁工具。

当前只提供朴素全局互斥锁 MutexLock，是租约锁改造前的基线。
"""

from lockfolio.lock import MutexLock

__all__ = ["MutexLock"]