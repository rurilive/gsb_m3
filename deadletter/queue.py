"""进程内死信队列。

消费失败的消息按重试上限沉淀到死信区，按失败原因分组，
可整批或按组重放；超保留期或超容量的死信挪入归档区。
消费者与时钟都从外部注入，纯标准库。
"""

import threading
import time


class DeadLetterQueue:
    """带重试上限的内存死信队列。

    handler: 消费者，签名 handler(msg)；正常返回视为成功，抛异常视为失败。
    max_retries: 同一条消息连续失败多少次后移入死信区。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    retention: 死信保留期（秒），sweep 时 dead_at 距今达到即归档；None 表示不过期。
    capacity: 死信区容量上限，sweep 时超出部分从最老的开始归档；None 表示不限。
    """

    def __init__(self, handler, max_retries=3, clock=time.monotonic,
                 retention=None, capacity=None):
        if max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        if retention is not None and retention <= 0:
            raise ValueError("retention must be > 0")
        if capacity is not None and capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._handler = handler
        self._max_retries = max_retries
        self._clock = clock
        self._retention = retention
        self._capacity = capacity
        self._lock = threading.Lock()
        # msg id -> 连续失败次数；成功后清零
        self._attempts = {}
        # 死信记录，按沉淀先后排列，最老的在前
        self._dead = []
        # 归档记录，按归档先后排列，最老的在前
        self._archive = []

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

    def groups(self):
        """当前死信区的分组键列表（按失败异常的类名，字典序）。"""
        with self._lock:
            return sorted({r["reason"] for r in self._dead})

    def dead_group(self, group):
        """指定分组的死信快照，返回新列表，记录逐条复制。"""
        with self._lock:
            return [dict(r) for r in self._dead if r["reason"] == group]

    def replay(self, group):
        """只把指定分组的死信再喂给 handler 一次，返回恢复条数。

        仍失败的退回原分组：attempts 累加 1 不清零，
        reason 与 dead_at 保持首次沉淀时的值。
        """
        with self._lock:
            pending = [r for r in self._dead if r["reason"] == group]
            self._dead = [r for r in self._dead if r["reason"] != group]
        recovered = 0
        failed = []
        for record in pending:
            try:
                self._handler(record["msg"])
            except Exception:
                record["attempts"] += 1
                failed.append(record)
            else:
                recovered += 1
        if failed:
            with self._lock:
                self._dead.extend(failed)
        return recovered

    def sweep(self):
        """维护死信区：先归档达到保留期的死信，再按容量上限从最老归档。

        归档记录附加 archived_at 与 cause（expired/overflow），返回归档条数。
        """
        now = self._clock()
        with self._lock:
            count = 0
            if self._retention is not None:
                keep = []
                for record in self._dead:
                    if now - record["dead_at"] >= self._retention:
                        self._archive.append(
                            self._archive_record(record, now, "expired"))
                        count += 1
                    else:
                        keep.append(record)
                self._dead = keep
            if self._capacity is not None:
                count += self._enforce_capacity(now)
            return count

    def archived(self, group=None):
        """归档区快照；给 group 时只返回该分组。新列表，记录逐条复制。"""
        with self._lock:
            return [dict(r) for r in self._archive
                    if group is None or r["reason"] == group]

    def _record(self, msg, attempts, exc):
        return {
            "msg": msg,
            "attempts": attempts,
            "reason": type(exc).__name__,
            "detail": str(exc),
            "dead_at": self._clock(),
        }

    def _archive_record(self, record, now, cause):
        archived = dict(record)
        archived["archived_at"] = now
        archived["cause"] = cause
        return archived

    def _enforce_capacity(self, now):
        count = 0
        while len(self._dead) > self._capacity:
            self._archive.append(
                self._archive_record(self._dead.pop(0), now, "overflow"))
            count += 1
        return count
