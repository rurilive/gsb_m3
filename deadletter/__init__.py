"""deadletter: 消息消费链路的进程内死信兜底。

消费失败的消息按重试上限沉淀到死信区，可整批重放。
"""

from deadletter.queue import DeadLetterQueue

__all__ = ["DeadLetterQueue"]
