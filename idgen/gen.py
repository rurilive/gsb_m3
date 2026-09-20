"""本地 ID 生成器：毫秒时间戳左移 16 位，低 16 位 = 实例号(4) + 自增计数(12)。"""
import os
import socket
import threading
import time

TIMESTAMP_SHIFT = 16
INSTANCE_BITS = 4
COUNTER_BITS = TIMESTAMP_SHIFT - INSTANCE_BITS
INSTANCE_MASK = (1 << INSTANCE_BITS) - 1
COUNTER_MASK = (1 << COUNTER_BITS) - 1
EPOCH_MS = 1700000000000
DEFAULT_MAX_WAIT_MS = 1000


class ClockMovedBackwardsError(RuntimeError):
    """时钟回拨过久且自增位已打满，拒绝冒险出号。"""


class InstanceIdInUseError(RuntimeError):
    """实例号已被另一个存活实例占用。"""


class FileInstanceRegistry:
    """共享目录里的实例号登记：启动占位 + 周期心跳，同号活实例立即报错。"""

    def __init__(self, directory, stale_ms=10000, clock=time.time):
        self._dir = directory
        self._stale_ms = stale_ms
        self._clock = clock
        os.makedirs(directory, exist_ok=True)

    def _path(self, instance_id):
        return os.path.join(self._dir, "instance-%d.claim" % instance_id)

    def _now_ms(self):
        return int(self._clock() * 1000)

    def _write(self, instance_id, owner):
        path = self._path(instance_id)
        tmp = path + ".tmp.%d" % os.getpid()
        with open(tmp, "w") as f:
            f.write("%s:%d" % (owner, self._now_ms()))
        os.replace(tmp, path)

    def claim(self, instance_id, owner):
        path = self._path(instance_id)
        try:
            with open(path, "r") as f:
                old_owner, _, ts = f.read().rpartition(":")
                old_ts = int(ts)
        except (OSError, ValueError):
            old_owner, old_ts = None, 0
        if old_owner and old_owner != owner and self._now_ms() - old_ts < self._stale_ms:
            raise InstanceIdInUseError(
                "instance_id %d already claimed by %s" % (instance_id, old_owner))
        self._write(instance_id, owner)

    def heartbeat(self, instance_id, owner):
        self._write(instance_id, owner)

    def release(self, instance_id, owner):
        path = self._path(instance_id)
        try:
            with open(path, "r") as f:
                old_owner = f.read().rpartition(":")[0]
            if old_owner == owner:
                os.remove(path)
        except OSError:
            pass


class IdGenerator:
    def __init__(self, clock=time.time, instance_id=0, registry=None,
                 max_wait_ms=DEFAULT_MAX_WAIT_MS, owner=None):
        if not 0 <= instance_id <= INSTANCE_MASK:
            raise ValueError("instance_id must be in [0, %d]" % INSTANCE_MASK)
        self._clock = clock
        self._instance_id = instance_id
        self._max_wait_ms = max_wait_ms
        self._lock = threading.Lock()
        self._last_ms = 0
        self._counter = 0
        self._registry = registry
        self._owner = owner or "%s-%d" % (socket.gethostname(), os.getpid())
        self._stop_heartbeat = threading.Event()
        self._heartbeat_thread = None
        if registry is not None:
            registry.claim(instance_id, self._owner)
            self._start_heartbeat(registry)

    def _start_heartbeat(self, registry):
        interval = max(registry._stale_ms / 3000.0, 0.5)

        def beat():
            while not self._stop_heartbeat.wait(interval):
                registry.heartbeat(self._instance_id, self._owner)

        self._heartbeat_thread = threading.Thread(target=beat, daemon=True)
        self._heartbeat_thread.start()

    def close(self):
        self._stop_heartbeat.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=2)
        if self._registry is not None:
            self._registry.release(self._instance_id, self._owner)

    def _now_ms(self):
        return int(self._clock() * 1000)

    def _wait_next_ms(self, last_ms):
        deadline = time.monotonic() + self._max_wait_ms / 1000.0
        ms = self._now_ms()
        while ms <= last_ms:
            if time.monotonic() > deadline:
                raise ClockMovedBackwardsError(
                    "clock did not pass %d within %d ms" % (last_ms, self._max_wait_ms))
            time.sleep(0.0002)
            ms = self._now_ms()
        return ms

    def next_id(self):
        with self._lock:
            ms = self._now_ms()
            if ms < self._last_ms:
                ms = self._last_ms
            if ms == self._last_ms:
                self._counter += 1
                if self._counter > COUNTER_MASK:
                    ms = self._wait_next_ms(self._last_ms)
                    self._counter = 0
            else:
                self._counter = 0
            self._last_ms = ms
            return ((ms - EPOCH_MS) << TIMESTAMP_SHIFT) \
                | (self._instance_id << COUNTER_BITS) | self._counter
