"""时钟抽象：读时与等待统一走 Clock，便于测试注入。

单调钟用于度量经过的时间，墙钟用于对外展示的系统时刻。生产环境里
墙钟会被 NTP 校时来回拨动，单调钟不会。
"""
import threading
import time as _time
from abc import ABC, abstractmethod


class Clock(ABC):
    """时间源。"""

    @abstractmethod
    def monotonic(self) -> float:
        """返回单调递增的读数（秒），只用于度量经过的时间。"""

    @abstractmethod
    def time(self) -> float:
        """返回墙钟读数（秒），可能被校时拨动。"""

    @abstractmethod
    def sleep(self, seconds: float) -> None:
        """阻塞 seconds 秒。"""


class SystemClock(Clock):
    """进程默认时钟。"""

    def monotonic(self) -> float:
        return _time.monotonic()

    def time(self) -> float:
        return _time.time()

    def sleep(self, seconds: float) -> None:
        _time.sleep(seconds)


class FakeClock(Clock):
    """手动推进的时钟，测试用。

    advance() 同时推进两个读数，代表真实时间流逝；jump_wall() 只拨墙钟，
    模拟 NTP 校时，单调钟读数不受影响。
    """

    def __init__(self, start: float = 0.0, wall: float = None):
        self._lock = threading.Lock()
        self._mono = float(start)
        self._wall = float(start if wall is None else wall)

    def monotonic(self) -> float:
        with self._lock:
            return self._mono

    def time(self) -> float:
        with self._lock:
            return self._wall

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self._mono += max(0.0, seconds)
            self._wall += max(0.0, seconds)

    def advance(self, seconds: float) -> None:
        """两个读数一起向前拨 seconds 秒。"""
        with self._lock:
            self._mono += seconds
            self._wall += seconds

    def jump_wall(self, delta: float) -> None:
        """只拨墙钟 delta 秒，模拟校时；单调钟不动。"""
        with self._lock:
            self._wall += delta
