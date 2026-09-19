"""命令栈：execute / undo / redo，事务与插入合并。"""

import time

from .commands import InsertText


def _monotonic_ms():
    return time.monotonic() * 1000


class _Batch:
    """事务提交后作为一条历史入栈的命令组。

    do() 按执行顺序重放，undo() 逆序撤销。
    """

    def __init__(self, commands):
        self.commands = list(commands)

    def do(self):
        for cmd in self.commands:
            cmd.do()

    def undo(self):
        for cmd in reversed(self.commands):
            cmd.undo()


class EditStack:
    """LIFO 命令栈。

    undo 之后执行新命令会截断重做分支——这是既定语义，
    历史永远沿"最后实际发生"的那条线走。

    coalesce_window_ms 大于 0 时，同 key 且首尾相接的连续 InsertText
    在窗口内合并为一条历史；clock 是返回毫秒的单调时钟，便于测试注入。
    """

    def __init__(self, coalesce_window_ms=0, clock=None):
        self._done = []    # 已执行的命令，栈顶是最近一条
        self._undone = []  # 被 undo 的命令，栈顶是下一个可重做的
        self._tx = None    # 事务中已执行的命令；None 表示不在事务里
        self._coalesce_window_ms = coalesce_window_ms
        self._clock = clock or _monotonic_ms
        self._last_execute_ms = None

    @property
    def can_undo(self):
        return bool(self._done)

    @property
    def can_redo(self):
        return bool(self._undone)

    @property
    def in_transaction(self):
        return self._tx is not None

    def begin(self):
        """开启事务；事务内 execute 照常生效但不入主栈。嵌套 begin 抛错。"""
        if self._tx is not None:
            raise RuntimeError("事务已开启，不支持嵌套 begin")
        self._tx = []

    def commit(self):
        """把事务内已执行的命令整批作为一条历史入栈并返回它；空事务返回 None。"""
        if self._tx is None:
            raise RuntimeError("没有进行中的事务，无法 commit")
        batch, self._tx = self._tx, None
        if not batch:
            return None
        entry = _Batch(batch)
        self._done.append(entry)
        return entry

    def rollback(self):
        """逆序撤销事务内已执行的命令并丢弃，不入历史。"""
        if self._tx is None:
            raise RuntimeError("没有进行中的事务，无法 rollback")
        batch, self._tx = self._tx, None
        for cmd in reversed(batch):
            cmd.undo()

    def execute(self, cmd):
        """执行一条命令并压入历史；重做分支同时被截断。

        事务中只执行不入主栈；非事务下满足合并条件时并入栈顶，
        否则作为新的一条历史压栈。
        """
        cmd.do()
        self._undone.clear()
        now = self._clock()
        if self._tx is not None:
            self._tx.append(cmd)
        elif not self._try_coalesce(cmd, now):
            self._done.append(cmd)
        self._last_execute_ms = now

    def _try_coalesce(self, cmd, now):
        """同 key、首尾相接且在窗口内的 InsertText 并入栈顶已合并文本。"""
        if self._coalesce_window_ms <= 0 or self._last_execute_ms is None:
            return False
        if now - self._last_execute_ms > self._coalesce_window_ms:
            return False
        top = self._done[-1] if self._done else None
        if (
            isinstance(top, InsertText)
            and isinstance(cmd, InsertText)
            and top.key == cmd.key
            and cmd.pos == top.pos + len(top.text)
        ):
            top.text += cmd.text
            return True
        return False

    def undo(self):
        """撤销最近一条命令并返回它；栈空时返回 None。"""
        if not self._done:
            return None
        cmd = self._done.pop()
        cmd.undo()
        self._undone.append(cmd)
        self._last_execute_ms = None
        return cmd

    def redo(self):
        """重做最近一条被撤销的命令并返回它；没有可重做时返回 None。"""
        if not self._undone:
            return None
        cmd = self._undone.pop()
        cmd.do()
        self._done.append(cmd)
        self._last_execute_ms = None
        return cmd
