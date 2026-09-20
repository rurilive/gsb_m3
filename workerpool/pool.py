"""固定大小线程池。

submit 把任务放进队列，size 个常驻工作线程逐个领取执行；
每个任务对应一个 Task 句柄，用来查状态、等落定、取结果。
"""

from atexit import register as _atexit_register
from concurrent.futures import CancelledError
import queue
import threading
import time

PENDING = "pending"
RUNNING = "running"
FINISHED = "finished"
FAILED = "failed"
CANCELLED = "cancelled"

# 工作线程的退出令牌；close 时每个线程投一个。
_SHUTDOWN_SENTINEL = object()


class PoolClosed(Exception):
    """池已关闭，submit / map 不再接收新任务。"""


class Task:
    """一次任务提交的句柄：状态、等待、结果。

    句柄在 submit 时创建，与执行进度无关；主线程拿到的
    Task 立刻可用，后续所有方法都线程安全。
    """

    def __init__(self, fn, args, kwargs, seq=0):
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._seq = seq
        self._state = PENDING
        self._result = None
        self._exception = None
        self._done = threading.Event()
        self._state_lock = threading.Lock()

    def __repr__(self):
        return f"<Task #{self._seq} {self._state}>"

    @property
    def fn(self):
        return self._fn

    @property
    def seq(self):
        """提交序号，从 0 起，池内单调递增。"""
        return self._seq

    @property
    def state(self):
        """PENDING / RUNNING / FINISHED / FAILED / CANCELLED 之一。"""
        return self._state

    @property
    def done(self):
        """任务是否已落定（成功、失败、取消都算）。"""
        return self._done.is_set()

    @property
    def cancelled(self):
        """任务是否在关闭时被取消（之后状态不再翻转）。"""
        return self._state == CANCELLED

    def wait(self, timeout=None):
        """等任务落定，返回是否在时限内落定。"""
        return self._done.wait(timeout)

    def result(self, timeout=None):
        """阻塞取结果；任务内抛出的异常在这里原样抛出。"""
        if not self._done.wait(timeout):
            raise TimeoutError("task not finished in time")
        if self._state == CANCELLED:
            raise CancelledError(
                f"task #{self._seq} was cancelled during shutdown"
            )
        if self._exception is not None:
            raise self._exception
        return self._result

    def exception(self, timeout=None):
        """阻塞取异常对象；任务成功时返回 None。"""
        if not self._done.wait(timeout):
            raise TimeoutError("task not finished in time")
        if self._state == CANCELLED:
            raise CancelledError(
                f"task #{self._seq} was cancelled during shutdown"
            )
        return self._exception

    def _cancel(self):
        # 只由持有池锁的 close 调用：未落定（含排队、在途）者标记取消。
        # 与 _run 用同一把锁竞争：落定（finished/failed）与取消只有一个赢家，
        # 取消后 _run 不再改写状态，保证取消后状态不再翻转。
        with self._state_lock:
            if self._done.is_set():
                return False
            self._state = CANCELLED
            self._done.set()
            return True

    def _run(self):
        # 只由工作线程调用：置状态、执行、写回结果。
        # 任务内异常在这里兜住，不向上杀死工作线程。
        # 排队期间已被取消的任务直接跳过，绝不执行。
        with self._state_lock:
            if self._done.is_set():
                return
            self._state = RUNNING

        # 在途任务无法硬中断：宽限期到期时可能已被标记 CANCELLED，
        # fn 仍在锁外跑完，但结束的 CAS 发现已取消就保持 CANCELLED、
        # 丢弃结果，状态不再翻转。
        try:
            result = self._fn(*self._args, **self._kwargs)
        except BaseException as exc:
            with self._state_lock:
                if self._done.is_set():
                    return
                self._exception = exc
                self._state = FAILED
                self._done.set()
        else:
            with self._state_lock:
                if self._done.is_set():
                    return
                self._result = result
                self._state = FINISHED
                self._done.set()


class WorkerPool:
    """固定大小线程池：size 个常驻线程共享一个任务队列。

    并发上限就是 size，多余的提交在队列里排队。
    atexit=True 时注册进程退出收尾，按 close() 语义等待全部落定。
    """

    def __init__(self, size, atexit=True):
        if size < 1:
            raise ValueError("size must be >= 1")
        self._queue = queue.SimpleQueue()
        self._tasks = []
        self._seq = 0
        self._closed = False
        self._close_report = None
        self._lock = threading.Lock()
        self._atexit_registered = bool(atexit)
        self._workers = [
            threading.Thread(target=self._worker_loop, daemon=True)
            for _ in range(size)
        ]
        for w in self._workers:
            w.start()
        if self._atexit_registered:
            _atexit_register(self._atexit_close)

    def _atexit_close(self):
        # 进程退出时按 close 语义收尾：不设时限，等全部任务落定。
        self.close()

    @property
    def size(self):
        return len(self._workers)

    @property
    def tasks(self):
        """全部已提交任务的句柄快照，按提交顺序；外部改不了内部列表。"""
        return tuple(self._tasks)

    @property
    def atexit_registered(self):
        """构造时是否注册了 atexit 收尾。"""
        return self._atexit_registered

    def submit(self, fn, *args, **kwargs):
        """提交任务，立即返回句柄，不等待执行。"""
        with self._lock:
            if self._closed:
                raise PoolClosed("worker pool is closed")
            task = Task(fn, args, kwargs, seq=self._seq)
            self._seq += 1
            self._tasks.append(task)
        self._queue.put(task)
        return task

    def map(self, fn, *iterables):
        """批量提交，阻塞到全部完成，按提交顺序返回结果列表。"""
        with self._lock:
            if self._closed:
                raise PoolClosed("worker pool is closed")
        tasks = [self.submit(fn, *item) for item in zip(*iterables)]
        return [t.result() for t in tasks]

    def wait_all(self, timeout=None):
        """等全部已提交任务落定，返回是否在时限内全部落定。

        只等待、不改变任何状态，也不影响新提交。
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        for t in self._tasks:
            if t.done:
                continue
            left = None if deadline is None else deadline - time.monotonic()
            if not t.wait(left):
                return False
        return True

    def close(self, grace_timeout=None):
        """优雅关闭。

        拒收新任务；已提交任务继续跑。grace_timeout=None 时无时限等
        全部落定；给定时限则等到期，未落定者（含排队的）标记
        CANCELLED，排队任务不再执行，句柄状态不再翻转。返回报告
        {"completed": 本次落定的任务数, "cancelled": 未完成句柄列表}。
        重复调用幂等，始终返回首次报告。
        """
        with self._lock:
            if self._close_report is not None:
                return self._close_report
            self._closed = True

            deadline = (
                None if grace_timeout is None
                else time.monotonic() + grace_timeout
            )
            settled = self._wait_settle(deadline)

            cancelled = []
            if not settled:
                for task in self._tasks:
                    if task._cancel():
                        cancelled.append(task)

            # 通知工作线程排空（跳过已取消任务）后退出。
            for _ in self._workers:
                self._queue.put(_SHUTDOWN_SENTINEL)

            report = {
                "completed": sum(
                    1 for task in self._tasks
                    if task.state != CANCELLED
                ),
                "cancelled": cancelled,
            }
            self._close_report = report
            return report

    def _wait_settle(self, deadline):
        # 等所有任务落定；deadline 到期返回 False。锁由 close 持有，
        # 工作线程照常执行，不与这里争锁。
        for task in self._tasks:
            if task.done:
                continue
            remaining = (
                None if deadline is None
                else deadline - time.monotonic()
            )
            if remaining is not None and remaining <= 0:
                return False
            if not task.wait(remaining):
                return False
        return True

    def _worker_loop(self):
        # 常驻循环：队列空就阻塞等待，收到退出令牌后结束。
        # 线程是 daemon，不阻塞进程退出。
        while True:
            task = self._queue.get()
            if task is _SHUTDOWN_SENTINEL:
                return
            task._run()
