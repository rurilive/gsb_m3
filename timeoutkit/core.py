"""调用编排：在预算内执行调用，支持超时与取消传播。

一次调用拿到一个 CallContext。调用可以从中派生更短的子上下文来限制
下游步骤，派生出的子上下文挂在父级下面：父级被取消时，子级一并作废。
"""
import threading
from typing import Any, Callable, Optional

from .clock import Clock, SystemClock
from .deadline import Deadline


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
        self._cancel_callbacks = []
        self._cancelled = False
        self._deadline = self._make_deadline(timeout, parent)
        if parent is not None:
            parent._register(self)

    def _make_deadline(self, timeout: Optional[float],
                       parent: Optional["CallContext"]) -> Optional[Deadline]:
        """构造预算：自身 timeout 与父级剩余预算取更紧的那个。

        不给 timeout 的子上下文继承父级截止时刻，否则父预算无法约束
        后代调用；给了 timeout 则换算成自身截止时刻，再与父级截止时刻
        取更早的，防止“父 800ms、子 5s”时子层自顾自跑满。
        """
        if parent is None:
            return Deadline(timeout, self._clock) if timeout is not None else None
        candidates = []
        if timeout is not None:
            candidates.append(Deadline(timeout, self._clock))
        if parent._deadline is not None:
            candidates.append(parent._deadline)
        if not candidates:
            return None
        return min(candidates, key=lambda deadline: deadline.remaining())

    # -- 预算 -----------------------------------------------------------

    def child(self, timeout: Optional[float] = None) -> "CallContext":
        """派生一个子上下文，可从 timeout 秒后到期。"""
        return CallContext(timeout=timeout, parent=self)

    def remaining(self) -> float:
        """当前上下文还剩多少秒预算；没有预算时返回 inf。"""
        if self._deadline is None:
            return float("inf")
        return self._deadline.remaining()

    def expired(self) -> bool:
        """预算是否已经耗尽。"""
        return self._deadline is not None and self._deadline.expired()

    # -- 取消 -----------------------------------------------------------

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def _register(self, child: "CallContext") -> None:
        with self._lock:
            self._children.append(child)
            already = self._cancelled
        if already:
            child.cancel()

    def _on_cancel(self, callback: Callable[[], None]) -> None:
        """注册取消回调；若已取消则立即同步调用。返回是否已取消。"""
        with self._lock:
            if self._cancelled:
                return True
            self._cancel_callbacks.append(callback)
            return False

    def _drop_cancel_callback(self, callback: Callable[[], None]) -> None:
        with self._lock:
            try:
                self._cancel_callbacks.remove(callback)
            except ValueError:
                pass

    def cancel(self) -> None:
        """取消本上下文以及所有派生出来的子上下文。"""
        with self._lock:
            if self._cancelled:
                return
            self._cancelled = True
            kids = list(self._children)
            callbacks = list(self._cancel_callbacks)
        for kid in kids:
            kid.cancel()
        for callback in callbacks:
            callback()

    def check(self) -> None:
        """协作式取消点：被取消时抛出 Cancelled。

        耗时较长的被调方应周期性调用它，以便及时响应取消。
        """
        if self._cancelled:
            raise Cancelled("context cancelled")
        if self._deadline is not None and self._deadline.expired():
            # 预算耗尽与取消同等处理：终止本层及全部子层的在途工作。
            self.cancel()
            raise Timeout("上下文预算已耗尽")

    def _aborted(self) -> bool:
        """是否已不可再用：显式取消或预算耗尽。"""
        return self._cancelled or (self._deadline is not None and self._deadline.expired())

    # -- 调用 -----------------------------------------------------------

    def call(self, fn: Callable[[], Any], timeout: Optional[float] = None) -> Any:
        """在本次上下文中（或其子预算下）执行 fn。"""
        return call(fn, timeout=timeout, ctx=self)


def _run(fn: Callable[[], Any], job: _Job, wake: threading.Event, ctx: "CallContext") -> None:
    try:
        # 线程已经起来、fn 尚未开跑的窗口里若上下文已作废，就不要再发起调用。
        if not ctx._aborted():
            job.value = fn()
    except BaseException as exc:  # noqa: BLE001 - 原样带回调用方
        job.error = exc
    finally:
        job.done.set()
        wake.set()


def call(fn: Callable[[], Any], timeout: Optional[float] = None,
         ctx: Optional[CallContext] = None) -> Any:
    """在 ctx 的预算内执行 fn，超出预算抛 Timeout。

    没有 ctx 时按 timeout 新建一个根上下文；上下文与 timeout 都给定时，
    取两者中更紧的那个。

    已取消的上下文会立刻抛 Cancelled，不会再发起新调用；预算耗尽的
    上下文立刻抛 Timeout。等待期间若上下文被（父级）取消，调用立刻以
    Cancelled 返回。调用超时时，所在上下文会被一并取消，使同一上下文
    里的协作式下游步骤及时停手，而不是在后台继续跑。
    """
    if ctx is None:
        ctx = CallContext(timeout=timeout)
    elif timeout is not None:
        ctx = ctx.child(timeout)

    if ctx.cancelled:
        raise Cancelled("context cancelled")
    if ctx.expired():
        ctx.cancel()
        raise Timeout("调用超出 %s 秒预算" % timeout)

    job = _Job()
    wake = threading.Event()

    def _wake() -> None:
        wake.set()

    if ctx._on_cancel(_wake):
        raise Cancelled("context cancelled")

    worker = threading.Thread(target=_run, args=(fn, job, wake, ctx), daemon=True)
    worker.start()

    try:
        while True:
            if job.done.is_set():
                break
            if ctx.cancelled:
                raise Cancelled("context cancelled")
            budget = ctx.remaining()
            if budget != float("inf") and budget <= 0.0:
                ctx.cancel()
                raise Timeout("调用超出 %s 秒预算" % timeout)
            # 完成事件与取消回调都会唤醒 wake：无预算时一直等到二者之一，
            # 有预算时最多等到预算耗尽，取消仍可即时打断。
            wake.wait(timeout=None if budget == float("inf") else budget)
            wake.clear()

        if job.error is not None:
            raise job.error
        return job.value
    finally:
        ctx._drop_cancel_callback(_wake)
