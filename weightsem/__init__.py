"""weightsem: 一个朴素计数信号量。

现在只有 Semaphore 这一把普通计数信号量，见 weightsem/semaphore.py。
加权获取、可超时、公平排队、可重入与动态缩容见任务描述。
"""

from .semaphore import Semaphore, SemaphoreBusy

__all__ = ["Semaphore", "SemaphoreBusy"]