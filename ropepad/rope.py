"""rope：叶子块拼起来的文本结构，眼下只跑得动退化的单叶子形态。

轮廓已经画好：Leaf 是一段只读正文，Branch 缓存子树长度。但 Rope 把整段正文
塞进一个叶子，insert / delete 整串重造，concat / slice 也只是整串抄一份：
结构上叫 rope，性能上还是 TextDoc，没碰到的叶子一个都留不下，叶子个数永远是 1。
位置一律是字符下标（多字节字符算一个位置），边界语义见任务描述与 TextDoc。
"""

from ropepad.errors import RangeError

MAX_LEAF = 1024
"""单个叶子的字符数上限。叶子超过这个数就该拆开，别让一块无限膨胀。"""


class Node:
    """节点的共同约定：length 是这棵子树的字符数，缓存在节点上随时可查。"""

    __slots__ = ()

    @property
    def length(self):
        raise NotImplementedError


class Leaf(Node):
    """一段正文。叶子只读：拆开时生成新叶子，老对象留给别人接着用。"""

    __slots__ = ("_text",)

    def __init__(self, text):
        if not isinstance(text, str):
            raise TypeError("叶子的内容必须是 str")
        self._text = text

    @property
    def text(self):
        return self._text

    @property
    def length(self):
        return len(self._text)

    def split(self, pos):
        """在 pos 处切成两片，返回 (左, 右) 两个新叶子。0 <= pos <= length。"""
        if pos < 0 or pos > len(self._text):
            raise RangeError("切分点越界: %d" % pos)
        return Leaf(self._text[:pos]), Leaf(self._text[pos:])


class Branch(Node):
    """内部节点：左右子树加一段缓存长度。"""

    __slots__ = ("_left", "_right", "_length")

    def __init__(self, left, right):
        if left is None or right is None:
            raise ValueError("分支的两边都得有节点")
        self._left = left
        self._right = right
        self._length = left.length + right.length

    @property
    def left(self):
        return self._left

    @property
    def right(self):
        return self._right

    @property
    def length(self):
        return self._length


class Rope:
    """文本的 rope。接口口径和 TextDoc 一套，两边可以互相顶班。"""

    __slots__ = ("_root", "_copied")

    def __init__(self, root=None, copied=0):
        self._root = root
        self._copied = copied

    @classmethod
    def from_text(cls, text):
        """用一段正文起一条 rope。"""
        if not isinstance(text, str):
            raise TypeError("正文必须是 str")
        if not text:
            return cls()
        return cls(Leaf(text))

    def __len__(self):
        return self._root.length if self._root is not None else 0

    def depth(self):
        """树高：空 rope 是 0，单个叶子是 1。"""
        if self._root is None:
            return 0
        best = 0
        stack = [(self._root, 1)]
        while stack:
            node, level = stack.pop()
            if isinstance(node, Branch):
                stack.append((node.left, level + 1))
                stack.append((node.right, level + 1))
            elif level > best:
                best = level
        return best

    def leaf_ids(self):
        """按文档序给出所有叶子的 id()。验收拿它前后对比，统计叶子复用率。"""
        return [id(leaf) for leaf in self._leaves()]

    def locate(self, pos):
        """定位 pos 落在哪个叶子上，返回 (leaf, offset)。

        0 <= pos <= 长度；pos 等于长度时返回最右边的叶子、offset 等于叶子长度，
        空 rope 上只接受 pos 0 并返回 (None, 0)，越界抛 RangeError。节点上都缓存
        着子树长度，顺一条路径走到底就够，别把叶子过一遍。
        """
        n = len(self)
        if pos < 0 or pos > n:
            raise RangeError("定位越界: %d" % pos)
        if self._root is None:
            return (None, 0)
        # 退化形态：只有一个叶子，位置就是这个叶子里的小偏移。
        return (self._root, pos)

    def text(self):
        """物化整段正文。验收和调试用，编辑路径不该调。"""
        if self._root is None:
            return ""
        if isinstance(self._root, Leaf):
            return self._root.text
        return "".join(leaf.text for leaf in self._leaves())

    def stats(self):
        """指标字典：length 字符数，leaves 叶子个数，depth 树高（空 rope 为 0），
        copied 是本 rope 诞生以来构造与编辑真正新写出来的字符数，被复用的叶子不算，
        源对象的历史不继承。"""
        return {
            "length": len(self),
            "leaves": len(self.leaf_ids()),
            "depth": self.depth(),
            "copied": self._copied,
        }

    def slice(self, start, end):
        """取 [start, end) 做成新的 Rope，本对象不动，越界一律 RangeError。
        口径同 TextDoc.slice；副本里没改动的叶子该和本体共着用，两边各自独立。"""
        self._check_span(start, end)
        piece = self.text()[start:end]
        return Rope(Leaf(piece) if piece else None, copied=len(piece))

    def concat(self, other):
        """接在 other 后面，返回新的 Rope，两条老的都别动。"""
        if not isinstance(other, Rope):
            raise TypeError("只能和 Rope 拼接")
        text = self.text() + other.text()
        return Rope(Leaf(text) if text else None, copied=len(text))

    def insert(self, pos, text):
        """在 pos 处插入 text。pos 取 0 到长度（含）之外都抛 RangeError。"""
        if not isinstance(text, str):
            raise TypeError("插入的内容必须是 str")
        n = len(self)
        if pos < 0 or pos > n:
            raise RangeError("插入位置越界: %d" % pos)
        if not text:
            return
        merged = self.text()[:pos] + text + self.text()[pos:]
        self._root = Leaf(merged)
        self._copied += len(merged)

    def delete(self, start, count):
        """删掉 [start, start+count) 这段。count 为 0 是空操作，什么都不动。"""
        n = len(self)
        if count < 0 or start < 0 or start + count > n:
            raise RangeError("删除区间越界: %s" % ((start, count),))
        if count == 0:
            return
        merged = self.text()[:start] + self.text()[start + count:]
        self._root = Leaf(merged) if merged else None
        self._copied += len(merged)

    def iter_range(self, start, end):
        """按块迭代 [start, end) 的正文，每块一个 str，块长不超过 MAX_LEAF。
        start 负数或超过长度抛 RangeError，end 小于 start 也抛，end 超过长度截到
        末尾（这点和 slice 不同，口径照 TextDoc）；参数在取迭代器时当场校验，分块
        边界不作承诺，拼起来的内容必须一致。现在是先拼出整段再切，得改成顺树走。"""
        end = self._check_range(start, end)
        return self._chunks(start, end)

    def _chunks(self, start, end):
        text = self.text()[start:end]
        for i in range(0, len(text), MAX_LEAF):
            yield text[i:i + MAX_LEAF]

    def _leaves(self):
        """按文档序把叶子走一遍，显式栈，树再深也不炸。"""
        stack = []
        node = self._root
        while stack or node is not None:
            while node is not None:
                stack.append(node)
                node = node.left if isinstance(node, Branch) else None
            node = stack.pop()
            if isinstance(node, Leaf):
                yield node
                node = None
            else:
                node = node.right

    def _check_span(self, start, end):
        n = len(self)
        if start < 0 or end < 0 or start > end or end > n:
            raise RangeError("区间越界: %s，正文长度 %d" % ((start, end), n))

    def _check_range(self, start, end):
        n = len(self)
        if start < 0 or start > n or end < start:
            raise RangeError("区间越界: %s，正文长度 %d" % ((start, end), n))
        return min(end, n)
