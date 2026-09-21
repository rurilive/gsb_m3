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

`Rope` 是真正的 rope：`Leaf`（不超过 `MAX_LEAF` 个字符）拼成 AVL 平衡树，
`Branch` 缓存子树长度与树高。`insert` / `delete` / `slice` / `concat` 都是
路径拷贝：只重造受影响路径上的节点，没碰到的叶子原对象留着（id 不变），
新 rope 与源 rope 共享这些叶子、互相独立。`locate` 顺一条路径走到底，
`iter_range` 顺树按叶子吐块、不物化整段。顺序灌十万个小块树深也只有十几，
单次编辑的拷贝量与耗时不随正文长度涨（2 MB 正文上单字符插入约几微秒，
`copied` 只有几千，而 `TextDoc` 要抄整串）。

约束：`TextDoc` 与 `TextBuffer` 的既有接口、现有 `tests/` 的行为
一字不变，纯标准库。

## 运行

```bash
python3 demo.py                           # 看看现状：叶子复用、标记、耗时
python3 -m unittest discover -s tests -v  # 行为基线
```

`tests/test_rope_structure.py` 是 rope 的结构验收：按叶子 id 统计复用率、
树高上限、拷贝量对照 `TextDoc`、迭代内存峰值、随机编辑序列逐字符对拍。
