"""朴素同步执行器的实现（改造前基线）。

这里的执行器名字虽然叫池，但其实从不真正并发：每次提交都在调用线程里
立刻同步地把任务跑完，再把结果追加进一个结果列表，返回结果在列表中的
下标。没有工作线程，没有队列，没有结果凭据，也没有异常传递与超时。
"""


class SyncPool:
    """朴素同步执行器。

    内部只维护一个结果列表 ``_results``。提交时同步执行任务并把结果存进
    列表，返回该结果的下标；取结果按下标索引；等待是空操作。
    """

    def __init__(self):
        self._results = []

    # ---- 提交与执行 ----------------------------------------------------

    def submit(self, fn, arg):
        """同步执行 ``fn(arg)``，把结果存入结果列表并返回其下标。"""
        if not callable(fn):
            raise TypeError("fn 必须是可调用对象")
        result = fn(arg)
        self._results.append(result)
        return len(self._results) - 1

    def wait(self):
        """等待全部任务完成。当前是同步执行，故为空操作。"""
        return None

    # ---- 查询 ----------------------------------------------------------

    def results(self):
        """返回全部结果的浅拷贝，按提交先后排列。"""
        return list(self._results)

    def get(self, index):
        """返回第 ``index`` 个结果。"""
        return self._results[index]

    def size(self):
        """已提交（已执行）的任务个数。"""
        return len(self._results)

    # ---- 关闭 ----------------------------------------------------------

    def shutdown(self):
        """关闭执行器。当前为空操作。"""
        return None
