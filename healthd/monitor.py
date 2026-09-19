"""常驻自检：后台线程按周期跑探针，聚合出 ok/degraded/down。

与基线 CheckRunner 的区别：
- start()/stop() 起一个自检线程，每 period 秒跑一轮，间隔带 jitter 抖动；
- 注册探针可带 timeout，时限内没返回即判失败，不会拖死整轮；
- 通过数全部为 ok，达到门限 k 为 degraded，低于 k 为 down；
- ready() 按 k/n 门限回答「能不能接流量」，和「健不健康」分开；
- on_change(fn) 在整体状态翻转时于自检线程回调，回调抛错不影响检查。

时钟（time/sleep/Event）可注入，便于测试用假时钟定节奏。
"""

import random
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from healthd.board import ProbeResult, StatusBoard
from healthd.checker import CheckRunner, ProbeFn

OK = "ok"
DEGRADED = "degraded"
DOWN = "down"

ChangeFn = Callable[[str, str], None]


class LockedBoard(StatusBoard):
    """给基线状态板的每个方法加一把锁，供检查线程与读端点并发使用。"""

    def __init__(self):
        super().__init__()
        self._lock = threading.RLock()

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        with self._lock:
            super().record(name, ok, detail)

    def result(self, name: str) -> Optional[ProbeResult]:
        with self._lock:
            return super().result(name)

    def snapshot(self) -> Dict[str, ProbeResult]:
        with self._lock:
            return super().snapshot()

    def overall_ok(self) -> bool:
        with self._lock:
            return super().overall_ok()


class SystemClock:
    """默认时钟：真实墙钟。"""

    def time(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def event(self) -> threading.Event:
        return threading.Event()


class HealthMonitor(CheckRunner):
    """带常驻自检线程的检查运行器。"""

    def __init__(
        self,
        board: Optional[StatusBoard] = None,
        period: float = 5.0,
        jitter: float = 0.0,
        k: Optional[int] = None,
        clock=None,
        rng: Optional[Callable[[float, float], float]] = None,
    ):
        """period 为平均周期（秒），实际间隔在 [period-jitter, period+jitter]。

        k 是「可接流量」门限：>=k 个探针通过即 ready；k=None 表示要求全部通过。
        """
        if board is None:
            board = LockedBoard()
        super().__init__(board=board)
        if period <= 0:
            raise ValueError("period must be positive")
        if jitter < 0 or jitter > period:
            raise ValueError("jitter must be in [0, period]")
        if k is not None and k <= 0:
            raise ValueError("k must be positive or None")
        self._period = period
        self._jitter = jitter
        self._k = k
        self.clock = clock if clock is not None else SystemClock()
        self._rng = rng if rng is not None else random.uniform

        self._timeouts: Dict[str, Optional[float]] = {}
        self._listeners: List[ChangeFn] = []
        self._state: str = DOWN
        self._lock = threading.RLock()
        self._stop_event = None
        self._thread: Optional[threading.Thread] = None

    def register(self, name: str, fn: ProbeFn, timeout: Optional[float] = None) -> None:
        """注册探针。timeout 秒内没返回即判失败；None 表示不限制（基线行为）。"""
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout must be positive or None")
        with self._lock:
            super().register(name, fn)
            self._timeouts[name] = timeout

    def start(self) -> None:
        """起后台自检线程；立即跑一轮，随后按抖动周期轮询。重复调用抛 RuntimeError。"""
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("monitor already started")
            self._stop_event = self.clock.event()
            self._thread = threading.Thread(
                target=self._loop, name="healthd-monitor", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        """通知自检线程退出并等待其结束。重复调用无副作用。"""
        with self._lock:
            thread = self._thread
            stop_event = self._stop_event
        if thread is None:
            return
        stop_event.set()
        thread.join()
        with self._lock:
            if self._thread is thread:
                self._thread = None
                self._stop_event = None

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def on_change(self, fn: ChangeFn) -> None:
        """注册整体状态翻转回调 fn(old, new)，在自检线程里调用。"""
        with self._lock:
            self._listeners.append(fn)

    def status(self) -> str:
        """最近一轮聚合状态：ok / degraded / down（首轮前为 down）。"""
        with self._lock:
            return self._state

    def quorum(self) -> int:
        """当前生效的通过门限 k（探针总数下 k=None 即要求全部）。"""
        with self._lock:
            total = len(self._order)
            return total if self._k is None else min(self._k, total)

    def ready(self) -> bool:
        """能不能接流量：最近一轮通过探针数 >= k/n 门限即为 True。"""
        with self._lock:
            if not self._order:
                return False
            snap = self.board.snapshot()
            passed = sum(1 for r in snap.values() if r.ok)
            total = len(self._order)
            k = total if self._k is None else self._k
            return passed >= min(k, total)

    def snapshot(self) -> Dict[str, ProbeResult]:
        """状态板快照（线程安全，委托给加锁状态板）。"""
        with self._lock:
            return self.board.snapshot()

    def _next_delay(self) -> float:
        return self._rng(self._period - self._jitter, self._period + self._jitter)

    def _loop(self) -> None:
        stop_event = self._stop_event
        while not stop_event.is_set():
            self._run_round()
            delay = self._next_delay()
            deadline = self.clock.time() + delay
            while not stop_event.is_set():
                remaining = deadline - self.clock.time()
                if remaining <= 0:
                    break
                if stop_event.wait(remaining):
                    break

    def _run_round(self) -> None:
        with self._lock:
            names = list(self._order)
            timeouts = dict(self._timeouts)
        for name in names:
            probe = self._probes[name]
            ok, detail = self._run_probe(name, probe.fn, timeouts.get(name))
            self.board.record(name, ok, detail)
        self._aggregate(names)

    @staticmethod
    def _run_probe(name: str, fn: ProbeFn, timeout: Optional[float]) -> Tuple[bool, str]:
        box: Dict[str, str] = {}

        def work():
            try:
                box["detail"] = fn() or ""
                box["ok"] = "1"
            except Exception as exc:
                box["detail"] = str(exc)
                box["ok"] = "0"

        worker = threading.Thread(target=work, name=f"healthd-probe-{name}", daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            return False, f"timeout after {timeout}s"
        return box.get("ok") == "1", box.get("detail", "")

    def _aggregate(self, names: List[str]) -> None:
        with self._lock:
            snap = self.board.snapshot()
            passed = sum(1 for n in names if (r := snap.get(n)) is not None and r.ok)
            total = len(names)
            k = total if self._k is None else self._k
            quorum = min(k, total)
            if total > 0 and passed == total:
                new_state = OK
            elif total > 0 and passed >= quorum:
                new_state = DEGRADED
            else:
                new_state = DOWN

            old_state = self._state
            changed = old_state != new_state
            if changed:
                self._state = new_state
            listeners = list(self._listeners)

        if changed:
            for fn in listeners:
                try:
                    fn(old_state, new_state)
                except Exception:
                    pass
