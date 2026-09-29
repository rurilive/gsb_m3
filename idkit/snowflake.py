"""分布式 ID 生成器的现有实现（时间戳 + 序列号）。

纯标准库，无外部依赖。时钟通过 now_ms 参数或 clock 回调注入，便于测试。

ID 位布局（低位到高位）：

- 序列号 seq：SEQUENCE_BITS 位，同一毫秒内递增，从 0 开始
- 节点位 node：NODE_BITS 位，标识生成器所属节点
- 时间戳：从 EPOCH_MS 起算的毫秒数，左移到节点位与序列号之上

generation 规则：先取当前毫秒，若大于上次使用的时间戳，则时间戳前进、
序列号从 0 起；若等于上次，则序列号加一；若序列号超过上限，抛
SequenceExhausted（自旋等待属于尚未实现的能力）。
"""

import threading

# 起点时间戳：2020-01-01T00:00:00Z
EPOCH_MS = 1577836800000

SEQUENCE_BITS = 12
NODE_BITS = 10

MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1
MAX_NODE = (1 << NODE_BITS) - 1


class IdError(Exception):
    """本模块所有异常的基类。"""


class SequenceExhausted(IdError):
    """同一毫秒内序列号已用尽。"""


class ClockBackwards(IdError):
    """检测到时钟回拨。"""


class SnowflakeGenerator:
    """按时间戳与序列号生成单调递增的 64 位 ID。

    参数：
        node_id   节点编号，取值 0..MAX_NODE
        clock     取当前毫秒的回调，默认用 time.time() * 1000
    """

    def __init__(self, node_id=0, clock=None):
        if not isinstance(node_id, int) or isinstance(node_id, bool):
            raise TypeError("node_id must be an int")
        if node_id < 0 or node_id > MAX_NODE:
            raise ValueError("node_id out of range: %d" % node_id)
        self._node_id = node_id
        self._clock = clock if clock is not None else _default_clock
        self._lock = threading.RLock()
        self._last_ts = -1
        self._sequence = 0

    # -- 只读属性 --------------------------------------------------------

    @property
    def node_id(self):
        return self._node_id

    @property
    def last_timestamp(self):
        """最近一次使用的时间戳，还没生成过时为 -1。"""
        with self._lock:
            return self._last_ts

    # -- 生成 ------------------------------------------------------------

    def next_id(self, now_ms=None):
        """生成下一个 ID。

        now_ms 为空时向 clock 询问当前毫秒。时间戳前进则序列号归零，
        时间戳不变则序列号加一，序列号超上限抛 SequenceExhausted。
        """
        with self._lock:
            ts = self._resolve_time(now_ms)
            if ts < self._last_ts:
                raise ClockBackwards(
                    "clock moved backwards: %d -> %d" % (self._last_ts, ts))
            if ts == self._last_ts:
                if self._sequence >= MAX_SEQUENCE:
                    raise SequenceExhausted(
                        "sequence exhausted at timestamp %d" % ts)
                self._sequence += 1
            else:
                self._sequence = 0
            self._last_ts = ts
            return self.compose(ts, self._node_id, self._sequence)

    def compose(self, timestamp, node_id, sequence):
        """把三部分拼成一个 ID。"""
        return ((timestamp - EPOCH_MS) << (NODE_BITS + SEQUENCE_BITS)) \
            | (node_id << SEQUENCE_BITS) | sequence

    def parse(self, value):
        """从 ID 反解出 (timestamp, node_id, sequence)。"""
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("id must be an int")
        if value < 0:
            raise ValueError("id must be non-negative")
        sequence = value & MAX_SEQUENCE
        node_id = (value >> SEQUENCE_BITS) & MAX_NODE
        timestamp = (value >> (NODE_BITS + SEQUENCE_BITS)) + EPOCH_MS
        return timestamp, node_id, sequence

    # -- 内部 ------------------------------------------------------------

    def _resolve_time(self, now_ms):
        if now_ms is None:
            now_ms = self._clock()
        if not isinstance(now_ms, int) or isinstance(now_ms, bool):
            raise TypeError("now_ms must be an int")
        return now_ms


def _default_clock():
    """默认时钟：系统毫秒。"""
    import time
    return int(time.time() * 1000)


__all__ = [
    "EPOCH_MS",
    "MAX_NODE",
    "MAX_SEQUENCE",
    "NODE_BITS",
    "SEQUENCE_BITS",
    "ClockBackwards",
    "IdError",
    "SequenceExhausted",
    "SnowflakeGenerator",
]