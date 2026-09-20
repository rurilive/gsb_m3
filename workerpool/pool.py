"""固定大小线程池。

submit 把任务放进队列，size 个常驻工作线程逐个领取执行；
每个任务对应一个 Task 句柄，用来查状态、等落定、取结果。
close 触发优雅关闭：拒收新任务，等已提交任务落定或到时取消。
"""

import atexit as _atexit
import queue
import threading
import time
from typing import NamedTuple

PENDING = "pending"
RUNNING = "running"
FINISHED = "finished"
FAILED = "failed"
CANCELLED = "cancelled"


class PoolClosed(Exception):
    """池已关闭：close 之后再 submit/map 抛出。"""


class ShutdownReport(NamedTuple):
    """close 的返回报告。

    completed: 本次 close 期间落定（finished/failed）的任务数；
    cancelled: 到时限仍未落定、被标记 Cancelled 的任务句柄列表。
    """

    completed: int
    cancelled: list


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
        """任务是否已落定（成功或失败都算）。"""
        return self._done.is_set()

    def wait(self, timeout=None):
        """等任务落定，返回是否在时限内落定。"""
        return self._done.wait(timeout)

    def result(self, timeout=None):
        """阻塞取结果；任务内抛出的异常在这里原样抛出。"""
        if not self._done.wait(timeout):
            raise TimeoutError("task not finished in time")
        if self._exception is not None:
            raise self._exception
        return self._result

    def exception(self, timeout=None):
        """阻塞取异常对象；任务成功时返回 None。"""
        if not self._done.wait(timeout):
            raise TimeoutError("task not finished in time")
        return self._exception

    def _run(self):
        # 只由工作线程调用：置状态、执行、写回结果。
        # 任务内异常在这里兜住，不向上杀死工作线程。
        # 已取消的任务不再执行；执行中被取消的，状态不再翻转。
        with self._state_lock:
            if self._state == CANCELLED:
                return
            self._state = RUNNING
        try:
            result = self._fn(*self._args, **self._kwargs)
        except BaseException as exc:
            with self._state_lock:
                if self._state != CANCELLED:
                    self._exception = exc
                    self._state = FAILED
                    self._done.set()
        else:
            with self._state_lock:
                if self._state != CANCELLED:
                    self._result = result
                    self._state = FINISHED
                    self._done.set()

    def _cancel(self):
        # 只由 close 调用：未落定的任务标记 CANCELLED 并放行等待者。
        # 返回 True 表示本次调用确实把它从未定置为取消。
        with self._state_lock:
            if self._done.is_set():
                return False
            self._state = CANCELLED
            self._done.set()
            return True


class WorkerPool:
    """固定大小线程池：size 个常驻线程共享一个任务队列。

    并发上限就是 size，多余的提交在队列里排队。
    atexit=True（默认）时注册退出钩子，进程退出时按 close() 语义收尾。
    """

    def __init__(self, size, atexit=True):
        if size < 1:
            raise ValueError("size must be >= 1")
        self._queue = queue.SimpleQueue()
        self._tasks = []
        self._seq = 0
        self._closed = False
        self._report = None
        self._submit_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._atexit_registered = False
        self._workers = [
            threading.Thread(target=self._worker_loop, daemon=True)
            for _ in range(size)
        ]
        for w in self._workers:
            w.start()
        if atexit:
            _atexit.register(self.close)
            self._atexit_registered = True

    @property
    def size(self):
        return len(self._workers)

    @property
    def atexit_registered(self):
        """是否已注册 atexit 退出钩子。"""
        return self._atexit_registered

    @property
    def tasks(self):
        """全部已提交任务的句柄快照，按提交顺序；外部改不了内部列表。"""
        return tuple(self._tasks)

    def submit(self, fn, *args, **kwargs):
        """提交任务，立即返回句柄，不等待执行。池关闭后抛 PoolClosed。"""
        with self._submit_lock:
            if self._closed:
                raise PoolClosed("pool is closed")
            task = Task(fn, args, kwargs, seq=self._seq)
            self._seq += 1
            self._tasks.append(task)
            self._queue.put(task)
            return task

    def map(self, fn, *iterables):
        """批量提交，阻塞到全部完成，按提交顺序返回结果列表。"""
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
        """优雅关闭：拒收新任务，收尾已提交任务，返回 ShutdownReport。

        grace_timeout=None 时不限时，等全部已提交任务落定；
        给定时限则等到期，未落定者（含排队中的）标记 CANCELLED，
        之后状态不再翻转，排队中的取消任务不再被执行。
        重复调用幂等，返回首次关闭的报告。
        """
        with self._close_lock:
            if self._report is not None:
                return self._report
            with self._submit_lock:
                self._closed = True
                tasks = list(self._tasks)
            pending = [t for t in tasks if not t.done]
            deadline = (
                None if grace_timeout is None else time.monotonic() + grace_timeout
            )
            for t in pending:
                left = None if deadline is None else deadline - time.monotonic()
                if left is not None and left <= 0:
                    break
                if not t.wait(left):
                    break
            cancelled = [t for t in pending if t._cancel()]
            completed = sum(1 for t in pending if t.done and t.state != CANCELLED)
            self._report = ShutdownReport(completed=completed, cancelled=cancelled)
            return self._report

    def _worker_loop(self):
        # 常驻循环：队列空就阻塞等待，线程是 daemon，不阻塞进程退出。
        while True:
            task = self._queue.get()
            task._run()
