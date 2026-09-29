"""histkit.recorder: 最朴素的线性撤销记录器。

HistRecorder 用一个列表 _states 顺序存放每一份状态快照，push 把当前
状态追加进去，undo 把当前状态退回上一步。它只能沿一个方向退，退过
之后没有反方向的 redo，也没有任何分组或容量概念。
"""


class HistRecorder:
    """线性快照式撤销记录器（基线实现）。

    内部只用一条列表保存状态，指针落在列表末位；push 追加一份新状态，
    undo 退回上一份。没有 redo、事务、合并与上限。
    """

    def __init__(self, initial=None):
        self._states = [initial]

    @property
    def state(self):
        """当前状态。"""
        return self._states[-1]

    @property
    def depth(self):
        """已经记录过的状态份数（含初始状态）。"""
        return len(self._states)

    def push(self, state):
        """记录一份新状态，成为当前状态。"""
        self._states.append(state)
        return state

    def undo(self):
        """退回上一份状态；已经在最初状态时返回当前状态。"""
        if len(self._states) <= 1:
            return self._states[0]
        self._states.pop()
        return self._states[-1]
