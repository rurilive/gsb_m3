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
