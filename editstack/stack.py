"""命令栈：execute / undo / redo，事务与插入合并。"""

import time

from .commands import Command, InsertText


class _Transaction(Command):
    """一批命令作为一条历史记录：do/undo 都整批生效。"""

    def __init__(self, commands):
        self.commands = list(commands)

    def do(self):
        for cmd in self.commands:
            cmd.do()

    def undo(self):
        for cmd in reversed(self.commands):
            cmd.undo()


def _monotonic_ms():
    return time.monotonic() * 1000.0


class EditStack:
    """LIFO 命令栈。

    undo 之后执行新命令会截断重做分支——这是既定语义，
    历史永远沿"最后实际发生"的那条线走。

    事务：begin() 之后 execute 照常生效但不入主栈，commit() 把
    整批压成一条历史（undo 一步撤整批），rollback() 逆序撤销并丢弃。
    嵌套 begin、无事务时 commit/rollback、事务内 undo/redo 均抛
    RuntimeError。

    合并：coalesce_window_ms > 0 时，同 key 的 InsertText 且新插入
    起点紧接栈顶已合并文本末尾、距上次 execute 不超过窗口毫秒数，
    就并入栈顶而不是新开一条历史。clock 是注入的单调时钟，返回毫秒。
    """

    def __init__(self, coalesce_window_ms=0, clock=None):
        self._done = []    # 已执行的命令，栈顶是最近一条
        self._undone = []  # 被 undo 的命令，栈顶是下一个可重做的
        self._coalesce_window_ms = coalesce_window_ms
        self._clock = clock or _monotonic_ms
        self._tx = None          # 事务进行时为已执行命令的列表，否则为 None
        self._last_exec_ms = None

    @property
    def can_undo(self):
        return bool(self._done)

    @property
    def can_redo(self):
        return bool(self._undone)

    def execute(self, cmd):
        """执行一条命令并压入历史；重做分支同时被截断。"""
        cmd.do()
        self._undone.clear()
        now = self._clock()
        if self._tx is not None:
            self._tx.append(cmd)
        elif not self._try_coalesce(cmd, now):
            self._done.append(cmd)
        self._last_exec_ms = now

    def _try_coalesce(self, cmd, now):
        """满足合并条件时把 cmd 并入栈顶 InsertText，返回是否已合并。"""
        if self._coalesce_window_ms <= 0 or self._last_exec_ms is None:
            return False
        if now - self._last_exec_ms > self._coalesce_window_ms:
            return False
        if not isinstance(cmd, InsertText) or not self._done:
            return False
        top = self._done[-1]
        if not isinstance(top, InsertText) or top.key != cmd.key:
            return False
        if cmd.pos != top.pos + len(top.text):
            return False
        top.text += cmd.text
        return True

    def begin(self):
        """开启事务；事务中再 begin 抛 RuntimeError。"""
        if self._tx is not None:
            raise RuntimeError("transaction already active")
        self._tx = []

    def commit(self):
        """把事务内已执行的命令整批压成一条历史；空事务不产生历史。"""
        if self._tx is None:
            raise RuntimeError("no active transaction")
        batch = self._tx
        self._tx = None
        self._last_exec_ms = None
        if batch:
            self._done.append(_Transaction(batch))

    def rollback(self):
        """逆序撤销事务内已执行的命令并丢弃，不进重做分支。"""
        if self._tx is None:
            raise RuntimeError("no active transaction")
        batch = self._tx
        self._tx = None
        self._last_exec_ms = None
        for cmd in reversed(batch):
            cmd.undo()

    def undo(self):
        """撤销最近一条命令并返回它；栈空时返回 None。"""
        if self._tx is not None:
            raise RuntimeError("transaction active: commit or rollback first")
        if not self._done:
            return None
        cmd = self._done.pop()
        cmd.undo()
        self._undone.append(cmd)
        self._last_exec_ms = None
        return cmd

    def redo(self):
        """重做最近一条被撤销的命令并返回它；没有可重做时返回 None。"""
        if self._tx is not None:
            raise RuntimeError("transaction active: commit or rollback first")
        if not self._undone:
            return None
        cmd = self._undone.pop()
        cmd.do()
        self._done.append(cmd)
        self._last_exec_ms = None
        return cmd
