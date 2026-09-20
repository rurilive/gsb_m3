"""调用编排：在预算内执行调用，支持超时与取消传播。

一次调用拿到一个 CallContext。调用可以从中派生更短的子上下文来限制
下游步骤，派生出的子上下文挂在父级下面：父级被取消时，子级一并作废。
"""
import threading
from typing import Any, Callable, Optional

from .clock import Clock, SystemClock
from .deadline import Deadline

_POLL_INTERVAL = 0.01


class Cancelled(Exception):
    """上下文已经被取消，不再接受新调用。"""


class Timeout(Exception):
    """调用超出了所属上下文的预算。"""


class _Job:
    """一次后台执行的挂载点。"""

    __slots__ = ("done", "value", "error")

    def __init__(self):
        self.done = threading.Event()
        self.value = None
        self.error = None


class CallContext:
    """调用上下文：携带预算、父子关系与取消状态。"""

    def __init__(self, clock: Optional[Clock] = None, timeout: Optional[float] = None,
                 parent: Optional["CallContext"] = None):
        if clock is not None:
            self._clock = clock
        elif parent is not None:
            self._clock = parent._clock
        else:
            self._clock = SystemClock()
        self._parent = parent
        self._lock = threading.RLock()
        self._children = []
        self._cancelled = False
        self._cancel_event = threading.Event()
        self._deadline = Deadline(timeout, self._clock) if timeout is not None else None
        if parent is not None:
            parent._register(self)

    # -- 预算 -----------------------------------------------------------

    def child(self, timeout: Optional[float] = None) -> "CallContext":
        """派生一个子上下文，可从 timeout 秒后到期。"""
        return CallContext(timeout=timeout, parent=self)

    def remaining(self) -> float:
        """当前上下文还剩多少秒预算；没有预算时返回 inf。"""
        own = float("inf") if self._deadline is None else self._deadline.remaining()
        if self._parent is not None:
            # 预算沿父链取最紧：父级剩多少，子级最多只能用多少
            return min(own, self._parent.remaining())
        return own

    def expired(self) -> bool:
        """预算是否已经耗尽。"""
        if self._deadline is not None and self._deadline.expired():
            return True
        return self._parent is not None and self._parent.expired()

    # -- 取消 -----------------------------------------------------------

    @property
    def cancelled(self) -> bool:
        return self._is_cancelled()

    def _is_cancelled(self) -> bool:
        ctx = self
        while ctx is not None:
            if ctx._cancel_event.is_set():
                return True
            ctx = ctx._parent
        return False

    def _register(self, child: "CallContext") -> None:
        with self._lock:
            self._children.append(child)
            already = self._cancelled
        if already:
            child.cancel()

    def cancel(self) -> None:
        """取消本上下文以及所有派生出来的子上下文。"""
        with self._lock:
            if self._cancelled:
                return
            self._cancelled = True
            self._cancel_event.set()
            kids = list(self._children)
        for kid in kids:
            kid.cancel()

    def check(self) -> None:
        """协作式取消点：被取消时抛出 Cancelled。

        耗时较长的被调方应周期性调用它，以便及时响应取消。
        """
        if self._is_cancelled():
            raise Cancelled("context cancelled")

    # -- 调用 -----------------------------------------------------------

    def call(self, fn: Callable[[], Any], timeout: Optional[float] = None) -> Any:
        """在本次上下文中（或其子预算下）执行 fn。"""
        return call(fn, timeout=timeout, ctx=self)


def _run(fn: Callable[[], Any], job: _Job) -> None:
    try:
        job.value = fn()
    except BaseException as exc:  # noqa: BLE001 - 原样带回调用方
        job.error = exc
    finally:
        job.done.set()


def call(fn: Callable[[], Any], timeout: Optional[float] = None,
         ctx: Optional[CallContext] = None) -> Any:
    """在 ctx 的预算内执行 fn，超出预算抛 Timeout。

    没有 ctx 时按 timeout 新建一个根上下文；上下文与 timeout 都给定时，
    取两者中更紧的那个。
    """
    if ctx is None:
        ctx = CallContext(timeout=timeout)
    elif timeout is not None:
        ctx = ctx.child(timeout)

    # 已取消的上下文不再发起新调用
    ctx.check()

    job = _Job()
    worker = threading.Thread(target=_run, args=(fn, job), daemon=True)
    worker.start()

    while True:
        if job.done.is_set():
            break
        budget = ctx.remaining()
        if budget <= 0.0:
            raise Timeout("调用超出 %s 秒预算" % timeout)
        slice = _POLL_INTERVAL if budget == float("inf") else min(_POLL_INTERVAL, budget)
        job.done.wait(slice)
        # 被取消时尽快退出，而不是干等到预算耗尽
        ctx.check()

    if job.error is not None:
        raise job.error
    return job.value
