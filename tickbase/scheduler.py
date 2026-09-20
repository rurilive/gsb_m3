"""进程内调度器。

Scheduler 持有一组任务。add_task 注册时按触发器算好第一次触发时刻；
poll() 把到点的任务交给执行器派发，然后从当前时刻重算下一次触发时刻。
任务状态只活在进程里，进程重启后全部丢失，需要调用方自己重新注册。
"""

from .clock import SystemClock
from .executor import InlineExecutor


class Task:
    """注册进调度器的一个任务。"""

    def __init__(self, name, trigger, fn):
        self.name = name
        self.trigger = trigger
        self.fn = fn
        self.next_fire = None
        self.runs = 0

    def __repr__(self):
        return f"Task({self.name!r}, next_fire={self.next_fire})"


class Scheduler:
    """单进程调度器。"""

    def __init__(self, clock=None, executor=None):
        self._clock = clock if clock is not None else SystemClock()
        self._executor = executor if executor is not None else InlineExecutor()
        self._tasks = []
        self._by_name = {}

    # -- 注册与注销 ---------------------------------------------------

    def add_task(self, name, trigger, fn):
        """注册任务，第一次触发在一个触发周期之后。"""
        if name in self._by_name:
            raise ValueError(f"task name already used: {name}")
        task = Task(name, trigger, fn)
        task.next_fire = trigger.next_after(self._clock.now())
        self._tasks.append(task)
        self._by_name[name] = task
        return task

    def remove_task(self, name):
        """注销任务，返回被摘掉的 Task。"""
        task = self._by_name.pop(name)
        self._tasks.remove(task)
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
        fired = []
        for task in self._tasks:
            if task.next_fire is not None and task.next_fire <= now:
                self._dispatch(task, task.next_fire)
                fired.append(task.name)
                task.next_fire = task.trigger.next_after(self._clock.now())
        return fired

    def _dispatch(self, task, scheduled):
        """把一次触发交给执行器，任务函数收到的参数是计划触发时刻。"""
        self._executor.submit(lambda: task.fn(scheduled))
        task.runs += 1

    # -- 计数 ---------------------------------------------------------

    def stats(self):
        """累计计数：总的 runs，以及每个任务各跑了多少次。"""
        return {
            "runs": sum(t.runs for t in self._tasks),
            "per_task": {t.name: t.runs for t in self._tasks},
        }
