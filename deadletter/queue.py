"""进程内死信队列。

消费失败的消息按重试上限沉淀到死信区，可整批重放。
消费者与时钟都从外部注入，纯标准库。
"""

import threading
import time


class DeadLetterQueue:
    """带重试上限的内存死信队列。

    handler: 消费者，签名 handler(msg)；正常返回视为成功，抛异常视为失败。
    max_retries: 同一条消息连续失败多少次后移入死信区。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, handler, max_retries=3, clock=time.monotonic):
        if max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        self._handler = handler
        self._max_retries = max_retries
        self._clock = clock
        self._lock = threading.Lock()
        # msg id -> 连续失败次数；成功后清零
        self._attempts = {}
        # 死信记录，按沉淀先后排列，最老的在前
        self._dead = []

    def consume(self, msg):
        """尝试消费一条消息，返回是否成功。

        失败但未到上限时只累计次数；达到上限时整条移入死信区。
        handler 在锁外调用，避免消费者回调重入时死锁。
        """
        mid = msg["id"]
        error = None
        try:
            self._handler(msg)
        except Exception as exc:
            error = exc
        if error is None:
            with self._lock:
                self._attempts.pop(mid, None)
            return True
        with self._lock:
            n = self._attempts.get(mid, 0) + 1
            if n >= self._max_retries:
                self._dead.append(self._record(msg, n, error))
                self._attempts.pop(mid, None)
            else:
                self._attempts[mid] = n
            return False

    def dead(self):
        """死信区快照，返回新列表，记录本身也逐条复制。"""
        with self._lock:
            return [dict(r) for r in self._dead]

    def retry_dead(self):
        """把死信区每条消息再喂给 handler 一次。

        成功的移出死信区，仍失败的留在原位，返回恢复条数。
        """
        with self._lock:
            pending = list(self._dead)
        recovered = 0
        remain = []
        for record in pending:
            try:
                self._handler(record["msg"])
            except Exception:
                remain.append(record)
            else:
                recovered += 1
        with self._lock:
            self._dead = remain
        return recovered

    def _record(self, msg, attempts, exc):
        return {
            "msg": msg,
            "attempts": attempts,
            "reason": type(exc).__name__,
            "dead_at": self._clock(),
        }
