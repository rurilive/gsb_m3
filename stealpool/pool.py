"""每 worker 一条本地双端队列的工作窃取调度器，附带运行统计。

调度语义：

- 每个 worker 一条本地双端队列，自己在头部压入、从头部取活，
  别的 worker 从尾部偷（偷走的是最老的任务，子树通常最大）。
- worker 里派生的子任务进自己队列的头部，下一个就被自己拿到，
  线程本地的会话和解析缓存用得上；外部提交轮转到各队列尾部。
- worker 等子任务结果时不空等，转成帮忙模式：继续从本地队列和
  别的队列取活干，直到等的那个 future 落定，单 worker 跑深链也
  不会死锁。
- 取消一个没跑完的任务会顺着派生链级联：还没开跑的子孙任务一并
  作废，取结果抛 TaskCancelled；已经在干活的子孙不打断。
"""

import collections
import itertools
import os
import sys
import threading
import time

from stealpool.errors import PoolClosed
from stealpool.future import Future

# 本地统计每跑这么多任务刷进全局一次，省得每个任务都抢锁
_FLUSH_TASKS = 32

# 深链派生每层要占几层 Python 栈，递归上限抬高点深链才跑得完
_MIN_RECURSION_LIMIT = 32768


class Stats:
    """池的运行统计。

    busy / idle / tasks 按 worker 分槽，看负载匀不匀靠它们。
    """

    def __init__(self, workers):
        self._lock = threading.Lock()
        self._workers = workers
        self._submitted = self._completed = self._failed = self._steals = 0
        self._busy = [0.0] * workers
        self._idle = [0.0] * workers
        self._tasks = [0] * workers

    def submitted(self, n=1):
        with self._lock:
            self._submitted += n

    def steal(self, n=1):
        """记 n 次从别的 worker 那里取走任务。"""
        with self._lock:
            self._steals += n

    def flush(self, index, busy=0.0, idle=0.0, tasks=0, failed=0):
        """worker 把本地累计值刷进自己的槽位。

        tasks 是本批跑完的条数（含失败的），completed 只记成功的那部分。
        """
        with self._lock:
            self._busy[index] += busy
            self._idle[index] += idle
            self._tasks[index] += tasks
            self._completed += tasks - failed
            self._failed += failed

    def snapshot(self):
        with self._lock:
            return dict(
                workers=self._workers, submitted=self._submitted,
                completed=self._completed, failed=self._failed, steals=self._steals,
                busy_seconds=list(self._busy), idle_seconds=list(self._idle),
                tasks=list(self._tasks),
            )


class _Meter:
    """worker 线程本地的统计累计器，攒一批再刷进全局 Stats。"""

    __slots__ = ("stats", "index", "busy", "idle", "tasks", "failed", "since")

    def __init__(self, stats, index):
        self.stats = stats
        self.index = index
        self.busy = self.idle = 0.0
        self.tasks = self.failed = self.since = 0

    def add(self, busy=0.0, idle=0.0, tasks=0, failed=0):
        self.busy += busy
        self.idle += idle
        self.tasks += tasks
        self.failed += failed
        self.since += tasks
        if self.since >= _FLUSH_TASKS:
            self.flush()

    def flush(self):
        if self.busy or self.idle or self.tasks or self.failed:
            self.stats.flush(self.index, busy=self.busy, idle=self.idle,
                             tasks=self.tasks, failed=self.failed)
            self.busy = self.idle = 0.0
            self.tasks = self.failed = self.since = 0


class Pool:
    """固定线程数的工作窃取任务池。

    每个 worker 一条本地双端队列：自己从头取，别人从尾偷。
    接口和全局队列版一致，submit 返回 Future。
    """

    def __init__(self, workers=None, name="stealpool"):
        if workers is None:
            workers = os.cpu_count() or 1
        if workers < 1:
            raise ValueError("workers 至少为 1")
        if sys.getrecursionlimit() < _MIN_RECURSION_LIMIT:
            sys.setrecursionlimit(_MIN_RECURSION_LIMIT)
        self._worker_count = workers
        self._name = name
        self._deques = [collections.deque() for _ in range(workers)]
        self._stats = Stats(workers)
        self._cond = threading.Condition()
        self._closed = False
        self._idle = 0      # 睡在条件变量上等活的 worker 数
        self._helpers = 0   # 等在条件变量上的帮忙者数
        self._round_robin = itertools.count()
        self._local = threading.local()
        self._threads = []
        for index in range(workers):
            thread = threading.Thread(target=self._worker_main, args=(index,),
                                      name="%s-%d" % (name, index), daemon=True)
            thread.start()
            self._threads.append(thread)

    @property
    def workers(self):
        """线程数。"""
        return self._worker_count

    def submit(self, fn, *args, **kwargs):
        """提交一个任务，返回 Future。"""
        future = Future()
        future._pool = self
        future._cancel_hook = self._cascade_cancel
        index = getattr(self._local, "index", None)
        if index is None:
            # 外部提交：轮转到各队列尾部，天然摊开
            slot = next(self._round_robin) % self._worker_count
            at_head = False
        else:
            # worker 派生的子任务：挂到当前任务的子任务链上，进自己队列头部
            parent = getattr(self._local, "current", None)
            if parent is not None:
                with parent._condition:
                    parent._children.append(future)
            slot = index
            at_head = True
        with self._cond:
            if self._closed:
                raise PoolClosed("池已关闭，不能再提交任务")
            item = (future, fn, args, kwargs)
            if at_head:
                self._deques[slot].appendleft(item)
            else:
                self._deques[slot].append(item)
            self._stats.submitted()
            if self._idle or self._helpers:
                self._cond.notify()
        return future

    def shutdown(self, wait=True):
        """关闭池；wait 为真时等所有 worker 退出。可重复调用。"""
        with self._cond:
            self._closed = True
            self._cond.notify_all()
        if wait:
            for thread in self._threads:
                thread.join()

    def stats(self):
        """返回统计快照（含每 worker 的忙碌与空闲秒数）。"""
        return self._stats.snapshot()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.shutdown()

    # 内部实现 ----------------------------------------------------------

    def _next_item(self, index):
        """先取自己队列的头，空了再轮流从别人队列的尾偷。"""
        try:
            return self._deques[index].popleft()
        except IndexError:
            pass
        for offset in range(1, self._worker_count):
            victim = self._deques[(index + offset) % self._worker_count]
            try:
                item = victim.pop()
            except IndexError:
                continue
            self._stats.steal()
            return item
        return None

    def _execute(self, item, index):
        """跑一个任务，返回 (净忙碌秒数, 是否失败)；已取消的返回 None。"""
        future, fn, args, kwargs = item
        if not future.set_running_or_notify_cancel():
            return None
        previous = self._local.current
        self._local.current = future
        helped_before = self._local.helped_busy
        started = time.monotonic()
        try:
            value = fn(*args, **kwargs)
        except Exception as exc:
            failed = 1
            future.set_exception(exc)
        else:
            failed = 0
            future.set_result(value)
        finally:
            self._local.current = previous
        # 等待期间帮别人干活的时间不算在自己头上，避免和帮手的统计重复
        busy = time.monotonic() - started
        busy -= self._local.helped_busy - helped_before
        # 帮手入睡前会在条件锁内复查 future，这里也必须在锁内看 _helpers，
        # 否则可能错过刚要入睡的帮手
        with self._cond:
            if self._helpers:
                self._cond.notify_all()
        return max(busy, 0.0), failed

    def _worker_main(self, index):
        self._local.index = index
        self._local.current = None
        self._local.helped_busy = 0.0
        meter = _Meter(self._stats, index)
        while True:
            item = self._next_item(index)
            if item is None:
                meter.flush()
                with self._cond:
                    item = self._next_item(index)
                    while item is None and not self._closed:
                        self._idle += 1
                        waiting = time.monotonic()
                        self._cond.wait()
                        meter.add(idle=time.monotonic() - waiting)
                        self._idle -= 1
                        item = self._next_item(index)
                if item is None:
                    meter.flush()
                    return
            ran = self._execute(item, index)
            if ran is not None:
                meter.add(busy=ran[0], tasks=1, failed=ran[1])

    def _help_await(self, future, timeout):
        """worker 等 future 时顺手干活，直到 future 落定或超时。

        非 worker 线程（或 future 已落定）直接返回，走普通阻塞等待。
        """
        if getattr(self._local, "index", None) is None or future._settled:
            return
        index = self._local.index
        deadline = None if timeout is None else time.monotonic() + timeout
        meter = _Meter(self._stats, index)
        try:
            while not future._settled:
                item = self._next_item(index)
                if item is None:
                    meter.flush()
                    with self._cond:
                        item = self._next_item(index)
                        while item is None and not future._settled and not self._closed:
                            remaining = None
                            if deadline is not None:
                                remaining = deadline - time.monotonic()
                                if remaining <= 0:
                                    raise TimeoutError("等待任务结果超时")
                            self._helpers += 1
                            waiting = time.monotonic()
                            self._cond.wait(remaining)
                            meter.add(idle=time.monotonic() - waiting)
                            self._helpers -= 1
                            item = self._next_item(index)
                    if item is None:
                        break  # future 落定或池在关闭，交还给普通等待
                ran = self._execute(item, index)
                if ran is not None:
                    self._local.helped_busy += ran[0]
                    meter.add(busy=ran[0], tasks=1, failed=ran[1])
                if deadline is not None and not future._settled \
                        and time.monotonic() >= deadline:
                    raise TimeoutError("等待任务结果超时")
        finally:
            meter.flush()

    def _cascade_cancel(self, future):
        """取消某个任务时，把它派生出去还没开跑的子孙任务一并作废。"""
        with future._condition:
            children = list(future._children)
        for child in children:
            child.cancel()
