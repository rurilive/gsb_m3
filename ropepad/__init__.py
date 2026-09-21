"""ropepad：给编辑器件的文本缓冲。

doc.py 是整串实现的 TextDoc，rope.py 是准备顶掉它的 Rope（眼下还是退化形态），
buffer.py 是会话层，正文放在 doc 里，换实现时行为不变。
"""

from ropepad.buffer import TextBuffer
from ropepad.doc import CHUNK, TextDoc
from ropepad.errors import RangeError, TextError
from ropepad.rope import MAX_LEAF, Branch, Leaf, Node, Rope

__all__ = ["TextDoc", "CHUNK", "Rope", "Leaf", "Branch", "Node", "MAX_LEAF",
           "TextBuffer", "TextError", "RangeError"]
