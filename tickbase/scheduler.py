"""进程内调度器。

Scheduler 持有一组任务。add_task 注册时按触发器算好第一次触发时刻；
构造时给了 state_path 且状态文件里有同名任务的，接着落盘的计划时间恢复，
不从当前时刻重排。poll() 用最小堆只取到点的任务，不再全表扫描。
下一次触发时刻一律按上一次计划时间沿网格往前推，与 poll 时的时钟无关，
任务跑多久都不会带偏节奏；同一任务上一份没跑完就不会再派第二份。
时钟回拨只会让触发等待，不会重跑已经跑过的点。
"""

import heapq
import itertools
import json
import os

from .clock import SystemClock
from .executor import InlineExecutor

MISFIRE_POLICIES = ("coalesce", "skip")


class Task:
    """注册进调度器的一个任务。"""

    def __init__(self, name, trigger, fn, misfire, seq):
        self.name = name
        self.trigger = trigger
        self.fn = fn
        self.misfire = misfire
        self.seq = seq
        self.next_fire = None
        self.runs = 0
        self.skipped = 0
        self.coalesced = 0
        self.running = False

    def __repr__(self):
        return f"Task({self.name!r}, next_fire={self.next_fire})"


class Scheduler:
    """单进程调度器。

    state_path 给定时，每个任务的计划触发时刻会落盘（JSON，原子替换写入），
    进程重启后同名任务重新注册即按落盘的计划时间恢复。
    """

    def __init__(self, clock=None, executor=None, state_path=None):
        self._clock = clock if clock is not None else SystemClock()
        self._executor = executor if executor is not None else InlineExecutor()
        self._state_path = state_path
        self._state = self._load_state() if state_path is not None else {}
        self._tasks = []
        self._by_name = {}
        self._heap = []
        self._seq = itertools.count()
        self._dirty = False

    # -- 注册与注销 ---------------------------------------------------

    def add_task(self, name, trigger, fn, misfire="coalesce"):
        """注册任务，第一次触发在一个触发周期之后。

        misfire 决定停机或长任务错过多个计划点时怎么处理：
        "coalesce"（默认）合并补跑一次再回原节奏，"skip" 把错过的点直接丢掉。
        状态文件里有同名任务时，接着落盘的计划时间恢复，不从当前时刻重排。
        """
        if misfire not in MISFIRE_POLICIES:
            raise ValueError(f"unknown misfire policy: {misfire}")
        if name in self._by_name:
            raise ValueError(f"task name already used: {name}")
        task = Task(name, trigger, fn, misfire, next(self._seq))
        stored = self._state.get(name)
        if stored is not None:
            task.next_fire = stored
        else:
            task.next_fire = trigger.next_after(self._clock.now())
        self._tasks.append(task)
        self._by_name[name] = task
        heapq.heappush(self._heap, (task.next_fire, task.seq, task))
        if self._state_path is not None:
            self._state[name] = task.next_fire
            self._dirty = True
        return task

    def remove_task(self, name):
        """注销任务，返回被摘掉的 Task。"""
        task = self._by_name.pop(name)
        self._tasks.remove(task)
        if self._state_path is not None and name in self._state:
            del self._state[name]
            self._dirty = True
        return task

    def tasks(self):
        """当前注册的全部任务，按注册顺序。"""
        return list(self._tasks)

    def next_fire(self, name):
        """某个任务的下一次计划触发时刻。"""
        return self._by_name[name].next_fire

    # -- 推进 ---------------------------------------------------------

    def poll(self):
        """派发所有到点的任务，返回本次派发的任务名，按注册顺序。"""
        now = self._clock.now()
        due = []
        heap = self._heap
        while heap:
            fire_at, _, task = heap[0]
            if task.next_fire != fire_at or self._by_name.get(task.name) is not task:
                heapq.heappop(heap)  # 过期堆项：已注销或计划时间已更新
                continue
            if fire_at > now:
                break
            heapq.heappop(heap)
            due.append(task)
        due.sort(key=lambda t: t.seq)
        fired = []
        for task in due:
            if task.running:
                # 上一份还没跑完：不许叠着跑，计划点挂起等它跑完
                heapq.heappush(heap, (task.next_fire, task.seq, task))
                continue
            scheduled = task.next_fire
            next_fire, due_count = task.trigger.catch_up(scheduled, now)
            if task.misfire == "skip" and due_count > 1:
                task.skipped += due_count
            else:
                self._dispatch(task, scheduled)
                fired.append(task.name)
                if due_count > 1:
                    task.coalesced += due_count - 1
            task.next_fire = next_fire
            heapq.heappush(heap, (next_fire, task.seq, task))
            if self._state_path is not None:
                self._state[task.name] = next_fire
                self._dirty = True
        self.flush()
        return fired

    def _dispatch(self, task, scheduled):
        """把一次触发交给执行器，任务函数收到的参数是计划触发时刻。"""
        task.running = True

        def job():
            try:
                task.fn(scheduled)
            finally:
                task.running = False

        try:
            self._executor.submit(job)
        except BaseException:
            task.running = False
            raise
        task.runs += 1

    # -- 状态落盘 -----------------------------------------------------

    def _load_state(self):
        """读状态文件。文件不存在、坏了或只写了一半都当作空状态照常起来。"""
        try:
            with open(self._state_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            state = {}
            for name, entry in raw["tasks"].items():
                next_fire = entry["next_fire"]
                if isinstance(next_fire, (int, float)):
                    state[name] = float(next_fire)
            return state
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return {}

    def flush(self):
        """有未落盘的计划触发时刻时写状态文件（临时文件 + 原子替换）。"""
        if self._state_path is None or not self._dirty:
            return
        payload = {
            "version": 1,
            "tasks": {
                name: {"next_fire": next_fire}
                for name, next_fire in self._state.items()
            },
        }
        tmp_path = self._state_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp_path, self._state_path)
        self._dirty = False

    # -- 计数 ---------------------------------------------------------

    def stats(self):
        """累计计数：runs、每个任务的 runs，以及 misfire 的 skipped、coalesced。"""
        return {
            "runs": sum(t.runs for t in self._tasks),
            "per_task": {t.name: t.runs for t in self._tasks},
            "skipped": sum(t.skipped for t in self._tasks),
            "coalesced": sum(t.coalesced for t in self._tasks),
        }
