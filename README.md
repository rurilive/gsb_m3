# editstack

协作编辑器的本地历史模块，单进程内嵌，纯标准库，无外部依赖。

## 现状

`editstack/commands.py` 定义 `Buffer`（带 key 的文本缓冲）与文本命令
`InsertText` / `DeleteText`，命令基类 `Command` 约定 `do()` / `undo()`。
`editstack/stack.py` 的 `EditStack` 提供 `execute` / `undo` / `redo` 与
`can_undo` / `can_redo`；undo 之后执行新命令会截断重做分支，
历史永远沿最后实际发生的那条线走。

## 问题

历史粒度完全等于命令粒度：用户连打一串字母，撤销就得一步步来；
一组相关调整也无法作为一个整体回退，撤销历史很快变成噪音。

## 约定

- 基线行为不变：`tests/test_editstack.py` 一个字不改，原样全绿
- undo 后新编辑截断重做分支的语义保持
- 纯标准库

## 运行

```bash
python3 demo.py                          # 编辑与撤销/重做演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 事务：`begin()` 后 `execute` 照常执行、仍截断重做分支，但命令进事务暂存区而非主栈
- `commit()` 把整批包成一条 `_Transaction` 记录压栈，`undo` 一步逆序撤整批；空事务不产生历史
- `rollback()` 逆序调用各命令的 `undo()` 并丢弃，不进重做分支
- 嵌套 `begin`、无事务时 `commit`/`rollback`、事务内 `undo`/`redo` 均抛 `RuntimeError`
- 合并：`coalesce_window_ms > 0` 时，同 key 的 `InsertText` 且新插入起点紧接栈顶已合并
  文本末尾、距上次 `execute` 不超过窗口毫秒数，就把文本并入栈顶命令而非新开历史
- 时钟通过 `clock` 参数注入（返回毫秒的单调时钟），默认 `time.monotonic() * 1000`
- 窗口默认 0 即关闭；`undo`/`redo`/`commit`/`rollback` 会重置计时，合并链不跨这些操作
