# ropepad

给编辑器件的文本缓冲，纯标准库，无外部依赖。位置一律是字符下标（多字节字符算一个），
越界一律抛 `RangeError`。

## 用法

```python
from ropepad import Rope, TextBuffer, TextDoc

doc = TextDoc("hello world")          # 整串实现
doc.insert(5, ",")
doc.delete(0, 1)
piece = doc.slice(4, 9)               # 取一段，做出新的对象，本体不动

rope = Rope.from_text("hello world")  # 同一套接口
rope.insert(5, ",")
rope.delete(0, 1)
print(rope.text(), rope.depth(), rope.stats())

buf = TextBuffer("hello world")                       # 会话层，默认 TextDoc
buf = TextBuffer("hello world", make_doc=Rope.from_text)   # 换 rope 当后端
buf.set_mark("caret", 5)
buf.insert(0, "say: ")                # 标记黏右，落进删除区间的标记拉到起点
print(buf.text(), buf.mark("caret"), buf.revision)
```

## 现有能力

- `ropepad/doc.py`：`TextDoc`，正文就是一条 `str`。`insert` / `delete` 原地改，
  `slice` / `concat` 返回新对象，`iter_range` 按块迭代区间（`end` 超过长度截到末尾），
  `stats()` 给出长度与 `copied`（到底抄了多少字符）。
- `ropepad/rope.py`：`Leaf` / `Branch` 两种节点，节点上都缓存子树长度 `length`；
  `Rope` 的 `insert` / `delete` / `slice` / `concat` / `iter_range` / `locate` / `depth` /
  `leaf_ids` / `stats` 接口已经齐了，位置口径与 `TextDoc` 完全一致。
- `ropepad/buffer.py`：`TextBuffer`，正文 + 命名标记 + 修订号，`make_doc` 可以换后端。

## 现状

`Rope` 还只是退化形态：所有正文塞在一个叶子里，`insert` / `delete` 把整串重拼，
`slice` / `concat` 把整串抄一份。所以叶子个数永远是 1，编辑后叶子 id 全部换掉，
`stats()["copied"]` 与 `TextDoc` 一样随正文长度线性上涨，`locate` 也谈不上走树。
正文到几十 MB 后，一次编辑要几百毫秒。

## 目标

见任务描述。约束：`TextDoc` 与 `TextBuffer` 的既有接口、现有 `tests/` 的行为
一字不变，纯标准库。

## 运行

```bash
python3 demo.py                           # 看看现状：叶子复用、标记、耗时
python3 -m unittest discover -s tests -v  # 行为基线
```
