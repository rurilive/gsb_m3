"""多机房 Snowflake ID 生成器：时间戳 | 实例号 | 序列，单实例内严格单调。"""
import threading
import time

TIMESTAMP_BITS = 41
INSTANCE_BITS = 10
SEQUENCE_BITS = 12

MAX_INSTANCE_ID = (1 << INSTANCE_BITS) - 1
SEQUENCE_MASK = (1 << SEQUENCE_BITS) - 1

EPOCH_MS = 1700000000000
DEFAULT_MAX_ROLLBACK_MS = 10_000


class ClockMovedBackwardsError(RuntimeError):
    """时钟回拨超过容忍阈值时抛出。"""


class SnowflakeGenerator:
    def __init__(self, instance_id, clock=time.time,
                 max_rollback_ms=DEFAULT_MAX_ROLLBACK_MS, registry=None):
        if not 0 <= instance_id <= MAX_INSTANCE_ID:
            raise ValueError(
                "instance_id 必须在 0..%d 之间" % MAX_INSTANCE_ID)
        self._instance_id = instance_id
        self._clock = clock
        self._max_rollback_ms = max_rollback_ms
        self._lock = threading.Lock()
        self._last_ms = -1
        self._sequence = 0
        self._lease = registry.claim(instance_id) if registry else None

    @property
    def instance_id(self):
        return self._instance_id

    def _now_ms(self):
        return int(self._clock() * 1000)

    def _wait_next_ms(self, last_ms):
        ms = self._now_ms()
        while ms <= last_ms:
            time.sleep(0.0001)
            ms = self._now_ms()
        return ms

    def next_id(self):
        with self._lock:
            ms = self._now_ms()
            if ms < self._last_ms:
                if self._last_ms - ms > self._max_rollback_ms:
                    raise ClockMovedBackwardsError(
                        "时钟回拨 %d ms，超过容忍阈值 %d ms"
                        % (self._last_ms - ms, self._max_rollback_ms))
                ms = self._last_ms
            if ms == self._last_ms:
                self._sequence = (self._sequence + 1) & SEQUENCE_MASK
                if self._sequence == 0:
                    ms = self._wait_next_ms(self._last_ms)
            else:
                self._sequence = 0
            self._last_ms = ms
            return (((ms - EPOCH_MS) << (INSTANCE_BITS + SEQUENCE_BITS))
                    | (self._instance_id << SEQUENCE_BITS)
                    | self._sequence)

    def close(self):
        if self._lease:
            self._lease.release()
            self._lease = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
