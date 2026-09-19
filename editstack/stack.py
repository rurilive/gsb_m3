"""命令栈：execute / undo / redo。"""


class EditStack:
    """LIFO 命令栈。

    undo 之后执行新命令会截断重做分支——这是既定语义，
    历史永远沿"最后实际发生"的那条线走。
    """

    def __init__(self):
        self._done = []    # 已执行的命令，栈顶是最近一条
        self._undone = []  # 被 undo 的命令，栈顶是下一个可重做的

    @property
    def can_undo(self):
        return bool(self._done)

    @property
    def can_redo(self):
        return bool(self._undone)

    def execute(self, cmd):
        """执行一条命令并压入历史；重做分支同时被截断。"""
        cmd.do()
        self._done.append(cmd)
        self._undone.clear()

    def undo(self):
        """撤销最近一条命令并返回它；栈空时返回 None。"""
        if not self._done:
            return None
        cmd = self._done.pop()
        cmd.undo()
        self._undone.append(cmd)
        return cmd

    def redo(self):
        """重做最近一条被撤销的命令并返回它；没有可重做时返回 None。"""
        if not self._undone:
            return None
        cmd = self._undone.pop()
        cmd.do()
        self._done.append(cmd)
        return cmd
