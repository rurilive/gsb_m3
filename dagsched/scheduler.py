"""任务依赖 DAG 调度器的现有实现。

登记任务与任务之间的依赖边，提供拓扑排序与就绪判定。
依赖方向统一约定为「依赖 -> 任务」：一条边 u -> v 表示 u 完成后 v 才可运行。
"""

import heapq
import threading


class CycleError(ValueError):
    """加入依赖边会让图中出现环时抛出。"""


class UnknownTask(KeyError):
    """任务名未登记时抛出。"""


class DependencyNotFound(KeyError):
    """声明的依赖任务名未登记时抛出。"""


class Scheduler:
    """维护任务依赖关系，做拓扑排序与就绪判定。

    add_task(name)                         登记一个任务
    add_dependency(task, dep)              声明 task 依赖 dep
    topo_order()                           拓扑排序，返回任务名列表
    ready_tasks(done=None)                 依赖已全部完成、自身尚未在 done 中的任务
    detect_cycle()                         有环返回环上任务名列表，无环返回 None
    predecessors(name) / successors(name)  直接前驱与直接后继
    has_task(name) / tasks()               任务是否存在 / 全部任务名
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._succ = {}       # task -> 后继集合
        self._pred = {}       # task -> 前驱集合

    # -- 登记与查询 ------------------------------------------------------

    def add_task(self, name):
        """登记任务名为 name 的节点，重复登记不改动已有依赖。"""
        if not isinstance(name, str) or not name:
            raise ValueError("task name must be a non-empty string")
        with self._lock:
            if name not in self._succ:
                self._succ[name] = set()
                self._pred[name] = set()

    def has_task(self, name):
        with self._lock:
            return name in self._succ

    def tasks(self):
        with self._lock:
            return list(self._succ)

    def add_dependency(self, task, dep):
        """声明 task 依赖 dep，即一条 dep -> task 的边。"""
        with self._lock:
            if task not in self._succ:
                raise UnknownTask(task)
            if dep not in self._succ:
                raise DependencyNotFound(dep)
            if task == dep:
                raise CycleError("self dependency: %s" % task)
            if task in self._succ[dep]:
                raise CycleError("cycle detected by edge %s -> %s" % (dep, task))
            self._succ[dep].add(task)
            self._pred[task].add(dep)

    # -- 直接邻居 --------------------------------------------------------

    def predecessors(self, name):
        """返回直接在它之前执行的任务名集合。"""
        with self._lock:
            if name not in self._pred:
                raise UnknownTask(name)
            return set(self._pred[name])

    def successors(self, name):
        """返回直接依赖它的任务名集合。"""
        with self._lock:
            if name not in self._succ:
                raise UnknownTask(name)
            return set(self._succ[name])

    # -- 拓扑排序 --------------------------------------------------------

    def topo_order(self):
        """Kahn 算法拓扑排序。

        无前驱的任务用堆维护，出堆顺序为任务名字典序，因此同一张图
        多次调用的结果完全一致。图中有环时返回尚未排出的任务名列表，
        顺序同样是字典序，便于调用方看到哪里断掉。
        """
        with self._lock:
            indegree = {n: len(p) for n, p in self._pred.items()}
            heap = [n for n, d in indegree.items() if d == 0]
            heapq.heapify(heap)
            order = []
            while heap:
                n = heapq.heappop(heap)
                order.append(n)
                for m in sorted(self._succ[n]):
                    indegree[m] -= 1
                    if indegree[m] == 0:
                        heapq.heappush(heap, m)
            if len(order) != len(self._succ):
                rest = sorted(n for n in self._succ if indegree[n] > 0)
                return rest
            return order

    def detect_cycle(self):
        """返回环上任务名列表（字典序），无环返回 None。"""
        with self._lock:
            color = {}                      # 0 未访问 1 在栈上 2 已完成
            for start in sorted(self._succ):
                if color.get(start):
                    continue
                stack = [(start, iter(sorted(self._succ[start])))]
                color[start] = 1
                path = [start]
                while stack:
                    node, it = stack[-1]
                    advanced = False
                    for nxt in it:
                        if color.get(nxt, 0) == 1:
                            idx = path.index(nxt)
                            return sorted(path[idx:])
                        if color.get(nxt, 0) == 0:
                            color[nxt] = 1
                            path.append(nxt)
                            stack.append((nxt, iter(sorted(self._succ[nxt]))))
                            advanced = True
                            break
                    if not advanced:
                        color[node] = 2
                        stack.pop()
                        path.pop()
            return None

    # -- 就绪判定 --------------------------------------------------------

    def ready_tasks(self, done=None):
        """依赖已全部满足、自身尚未完成的任务名列表。

        done 为已完成任务名集合，缺省视作空集。
        """
        with self._lock:
            done = set(done) if done else set()
            out = []
            for name in sorted(self._succ):
                if name in done:
                    continue
                if self._pred[name] <= done:
                    out.append(name)
            return out