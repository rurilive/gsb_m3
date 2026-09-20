"""任务派发方式。

调度器不直接调用任务函数，而是把它交给执行器的 submit。
默认的 InlineExecutor 当场执行；想换线程池、队列或者测试里想推迟执行，
构造调度器时换一个带 submit(fn) 的执行器就行。
"""


class InlineExecutor:
    """提交即执行，执行完才返回。"""

    def submit(self, fn):
        return fn()
