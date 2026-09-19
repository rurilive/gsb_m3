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

- 事务：`begin()` 把 `_tx` 置为空列表，期间 `execute` 照常 `do()` 但只追加到
  `_tx`；`commit()` 把整批包成 `_Batch`（`do` 顺序重放、`undo` 逆序）作为一条
  历史压栈，`rollback()` 直接逆序 `undo()` 并丢弃，不入历史也不碰重做分支。
  嵌套 `begin`、无事务的 `commit`/`rollback` 均抛 `RuntimeError`。
- 合并：`coalesce_window_ms > 0` 时，新 `InsertText` 与栈顶同 key、起点等于
  栈顶 `pos + len(text)`、且距上次 `execute` 不超过窗口，就把文本并入栈顶，
  不产生新历史；窗口默认 0 关闭，`clock` 注入返回毫秒的单调时钟便于测试。
- `undo`/`redo` 会重置合并链；undo 后新编辑截断重做分支的语义不变。
