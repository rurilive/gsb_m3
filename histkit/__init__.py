"""histkit: 一个纯标准库的撤销记录小包。

当前只提供最朴素的线性撤销记录器 HistRecorder，用列表存快照，
只能 push 与 undo 一步，没有 redo、没有事务、没有命令合并、没有历史上限。
命令模式 undo/redo、命令合并、事务提交回滚、有限历史回收与状态跳转
见任务描述。
"""

from histkit.recorder import HistRecorder

__all__ = ["HistRecorder"]
