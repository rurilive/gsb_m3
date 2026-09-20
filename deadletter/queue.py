"""进程内死信队列。

消费失败的消息按重试上限沉淀到死信区，可整批或按失败原因分组重放。
死信有两条退出通道：超过保留期、超过容量上限的记录移入归档，
归档可按组查询。消费者与时钟都从外部注入，纯标准库。
"""

import threading
import time


class DeadLetterQueue:
    """带重试上限、分组重放与归档的内存死信队列。

    handler: 消费者，签名 handler(msg)；正常返回视为成功，抛异常视为失败。
    max_retries: 同一条消息连续失败多少次后移入死信区。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    retention: 死信保留期（与 clock 同单位）；入队与 sweep_retention 时，
         dead_at 距今达到保留期的记录按原因 "ttl" 归档，None 表示永不过期。
    max_dead: 死信区容量上限；新记录入队后超限时，最老的记录按原因
         "capacity" 归档，None 表示不限容量。
    """

    def __init__(self, handler, max_retries=3, clock=time.monotonic,
                 retention=None, max_dead=None):
        if max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        if retention is not None and retention <= 0:
            raise ValueError("retention must be > 0")
        if max_dead is not None and max_dead < 1:
            raise ValueError("max_dead must be >= 1")
        self._handler = handler
        self._max_retries = max_retries
        self._clock = clock
        self._retention = retention
        self._max_dead = max_dead
        self._lock = threading.Lock()
        # msg id -> 连续失败次数；成功后清零
        self._attempts = {}
        # 死信记录，按沉淀先后排列，最老的在前
        self._dead = []
        # 归档记录（含 cause / archived_at），按归档先后排列
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
                now = self._clock()
                self._admit(self._record(msg, n, error, now), now)
                self._attempts.pop(mid, None)
            else:
                self._attempts[mid] = n
            return False

    def dead(self):
        """死信区快照，返回新列表，记录本身也逐条复制。"""
        with self._lock:
            return [dict(r) for r in self._dead]

    def dead_groups(self):
        """按失败原因分堆的死信快照。

        返回 {reason: [记录副本, ...]}，只含当前非空的堆；
        记录顺序与沉淀先后一致，每条记录可翻回 msg 与失败上下文。
        """
        with self._lock:
            groups = {}
            for record in self._dead:
                groups.setdefault(record["reason"], []).append(dict(record))
            return groups

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

    def replay_group(self, reason):
        """只重放某一堆死信（按沉淀先后逐条喂给 handler）。

        成功的移出死信区；仍失败的退回原来那堆（分组键不变，即使这次
        抛出的是另一种异常），attempts 在原值上继续累加并刷新失败上下文，
        绝不重置。返回恢复条数；未知分组返回 0。
        """
        with self._lock:
            targets = [r for r in self._dead if r["reason"] == reason]
        recovered = 0
        failed = []
        for record in targets:
            try:
                self._handler(record["msg"])
            except Exception as exc:
                failed.append((record, exc))
            else:
                recovered += 1
        with self._lock:
            failed_ids = {id(record) for record, _ in failed}
            if failed:
                now = self._clock()
                for record, exc in failed:
                    record["attempts"] += 1
                    record["error"] = str(exc)
                    record["last_at"] = now
            recovered_ids = {id(record) for record in targets
                             if id(record) not in failed_ids}
            if recovered_ids:
                self._dead = [r for r in self._dead
                              if id(r) not in recovered_ids]
        return recovered

    def sweep_retention(self):
        """把超过保留期的死信移入归档，返回归档条数。

        dead_at 距今达到 retention 即清走；未配置 retention 时为空操作。
        新记录入队时也会先跑这一遍，再做容量归档。
        """
        with self._lock:
            if self._retention is None:
                return 0
            return self._sweep_retention_locked(self._clock())

    def archived(self, reason=None):
        """归档快照。

        传 reason 时返回该组被清走的记录列表；不传时返回
        {reason: [记录, ...]}。每条含原死信字段及 cause / archived_at，
        cause 为 "ttl"（保留期）或 "capacity"（容量上限）。
        """
        with self._lock:
            if reason is None:
                groups = {}
                for record in self._archive:
                    groups.setdefault(record["reason"], []).append(dict(record))
                return groups
            return [dict(r) for r in self._archive
                    if r["reason"] == reason]

    def _admit(self, record, now):
        """新死信入队：先清保留期，再入队，最后按容量从最老归档。"""
        if self._retention is not None:
            self._sweep_retention_locked(now)
        self._dead.append(record)
        if self._max_dead is not None:
            while len(self._dead) > self._max_dead:
                oldest = self._dead.pop(0)
                self._archive_record(oldest, "capacity", now)

    def _sweep_retention_locked(self, now):
        remaining = []
        count = 0
        for record in self._dead:
            if now - record["dead_at"] >= self._retention:
                self._archive_record(record, "ttl", now)
                count += 1
            else:
                remaining.append(record)
        self._dead = remaining
        return count

    def _archive_record(self, record, cause, now):
        archived = dict(record)
        archived["cause"] = cause
        archived["archived_at"] = now
        self._archive.append(archived)

    def _record(self, msg, attempts, exc, now):
        return {
            "msg": msg,
            "attempts": attempts,
            "reason": type(exc).__name__,
            "error": str(exc),
            "dead_at": now,
            "last_at": None,
        }
