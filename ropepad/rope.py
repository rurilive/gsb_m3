"""rope：叶子块拼成 AVL 平衡树的文本结构。

Leaf 是一段只读正文（不超过 MAX_LEAF 个字符），Branch 缓存子树长度与树高。
所有编辑都是路径拷贝：insert / delete / slice / concat 只重造受影响路径上的
节点，没碰到的叶子原对象留着，id 不变；新 rope 和源 rope 共享这些叶子，
两边各自独立，改一边不牵动另一边。拼接与再平衡走 AVL 的 join / split，
树高稳定在 O(log 叶子数)，顺序灌十万个小块深度也远低于 64。
位置一律是字符下标（多字节字符算一个位置），边界语义与 TextDoc 一致。
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
    """内部节点：左右子树，缓存子树长度与树高（AVL 不变式靠它维持）。"""

    __slots__ = ("_left", "_right", "_length", "_height")

    def __init__(self, left, right):
        if left is None or right is None:
            raise ValueError("分支的两边都得有节点")
        self._left = left
        self._right = right
        self._length = left.length + right.length
        self._height = max(_height(left), _height(right)) + 1

    @property
    def left(self):
        return self._left

    @property
    def right(self):
        return self._right

    @property
    def length(self):
        return self._length

    @property
    def height(self):
        return self._height


def _height(node):
    """节点高度：叶子算 1，空树算 0。"""
    if node is None:
        return 0
    return node.height if isinstance(node, Branch) else 1


def _join(left, right):
    """AVL 拼接：left 的文档序整体在 right 之前，合成一棵平衡树。

    两棵树高度差任意都成立；只重造两侧脊柱上的 O(|高差|) 个分支节点，
    叶子一个不动。两边都可以是 None。
    """
    if left is None:
        return right
    if right is None:
        return left
    lh, rh = _height(left), _height(right)
    if lh > rh + 1:
        return _balance(left.left, _join(left.right, right))
    if rh > lh + 1:
        return _balance(_join(left, right.left), right.right)
    return Branch(left, right)


def _balance(left, right):
    """把左右两棵平衡子树装到一个分支下，高度差不超过 2 时单/双旋转复原。"""
    lh, rh = _height(left), _height(right)
    if lh > rh + 1:
        if _height(left.left) >= _height(left.right):
            return Branch(left.left, Branch(left.right, right))
        mid = left.right
        return Branch(Branch(left.left, mid.left), Branch(mid.right, right))
    if rh > lh + 1:
        if _height(right.right) >= _height(right.left):
            return Branch(Branch(left, right.left), right.right)
        mid = right.left
        return Branch(Branch(left, mid.left), Branch(mid.right, right.right))
    return Branch(left, right)


def _balanced(leaves):
    """把一串叶子对折成平衡树；空列表返回 None。"""
    if not leaves:
        return None
    if len(leaves) == 1:
        return leaves[0]
    mid = len(leaves) // 2
    return Branch(_balanced(leaves[:mid]), _balanced(leaves[mid:]))


def _chunk_leaves(text):
    """把正文切成不超过 MAX_LEAF 的叶子串。"""
    return [Leaf(text[i:i + MAX_LEAF]) for i in range(0, len(text), MAX_LEAF)]


def _splice_leaf(leaf, pos, chunks):
    """在叶子内部 pos 处塞进 chunks（Leaf 列表），返回 (子树, copied)。

    优先并界：插入内容能并进左半或右半就不新开叶子，保持叶子致密。
    边界上整片复用原串（CPython 全切片返回原对象）时不计入 copied。
    """
    text = leaf.text
    pieces = [c.text for c in chunks]
    if pos > 0:
        head = text[:pos]
        if len(head) + len(pieces[0]) <= MAX_LEAF:
            pieces[0] = head + pieces[0]
        else:
            pieces.insert(0, head)
    if pos < len(text):
        tail = text[pos:]
        if len(pieces[-1]) + len(tail) <= MAX_LEAF:
            pieces[-1] = pieces[-1] + tail
        else:
            pieces.append(tail)
    copied = 0
    leaves = []
    for piece in pieces:
        if piece is not text:
            copied += len(piece)
        leaves.append(Leaf(piece))
    return _balanced(leaves), copied


def _insert_at(node, pos, chunks):
    """把 chunks（Leaf 列表）插进子树 pos 处，返回 (新子树, copied)。"""
    if isinstance(node, Leaf):
        return _splice_leaf(node, pos, chunks)
    if pos <= node.left.length:
        new, copied = _insert_at(node.left, pos, chunks)
        return _join(new, node.right), copied
    new, copied = _insert_at(node.right, pos - node.left.length, chunks)
    return _join(node.left, new), copied


def _delete_span(node, start, end):
    """删掉子树里 [start, end) 这段，返回 (新子树或 None, copied)。

    整棵被盖住的子树直接丢弃（copied 为 0），只有被部分删到的叶子
    会写出新字符。
    """
    if start <= 0 and end >= node.length:
        return None, 0
    if isinstance(node, Leaf):
        kept = node.text[:start] + node.text[end:]
        return Leaf(kept), len(kept)
    left_len = node.left.length
    left, right, copied = node.left, node.right, 0
    if start < left_len:
        left, c = _delete_span(node.left, start, min(end, left_len))
        copied += c
    if end > left_len:
        right, c = _delete_span(node.right, max(start, left_len) - left_len,
                                end - left_len)
        copied += c
    return _join(left, right), copied


def _slice_out(node, start, end):
    """取出子树里 [start, end) 这段做成新树，源树不动。

    整棵被覆盖的子树直接共享（copied 为 0），只有被切到边界的叶子
    会写出新字符。
    """
    if start <= 0 and end >= node.length:
        return node, 0
    if isinstance(node, Leaf):
        piece = node.text[start:end]
        return (Leaf(piece), len(piece)) if piece else (None, 0)
    left_len = node.left.length
    left, right, copied = None, None, 0
    if start < left_len:
        left, c = _slice_out(node.left, start, min(end, left_len))
        copied += c
    if end > left_len:
        right, c = _slice_out(node.right, max(start, left_len) - left_len,
                              end - left_len)
        copied += c
    return _join(left, right), copied


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
        return cls(_balanced(_chunk_leaves(text)))

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
        node = self._root
        while isinstance(node, Branch):
            if pos < node.left.length:
                node = node.left
            else:
                pos -= node.left.length
                node = node.right
        return (node, pos)

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
        if start == end:
            return Rope()
        root, copied = _slice_out(self._root, start, end)
        return Rope(root, copied=copied)

    def concat(self, other):
        """接在 other 后面，返回新的 Rope，两条老的都别动。"""
        if not isinstance(other, Rope):
            raise TypeError("只能和 Rope 拼接")
        return Rope(_join(self._root, other._root))

    def insert(self, pos, text):
        """在 pos 处插入 text。pos 取 0 到长度（含）之外都抛 RangeError。"""
        if not isinstance(text, str):
            raise TypeError("插入的内容必须是 str")
        n = len(self)
        if pos < 0 or pos > n:
            raise RangeError("插入位置越界: %d" % pos)
        if not text:
            return
        if self._root is None:
            self._root = _balanced(_chunk_leaves(text))
            self._copied += len(text)
            return
        self._root, copied = _insert_at(self._root, pos, _chunk_leaves(text))
        self._copied += copied

    def delete(self, start, count):
        """删掉 [start, start+count) 这段。count 为 0 是空操作，什么都不动。"""
        n = len(self)
        if count < 0 or start < 0 or start + count > n:
            raise RangeError("删除区间越界: %s" % ((start, count),))
        if count == 0:
            return
        self._root, copied = _delete_span(self._root, start, start + count)
        self._copied += copied

    def iter_range(self, start, end):
        """按块迭代 [start, end) 的正文，每块一个 str，块长不超过 MAX_LEAF。
        start 负数或超过长度抛 RangeError，end 小于 start 也抛，end 超过长度截到
        末尾（这点和 slice 不同，口径照 TextDoc）；参数在取迭代器时当场校验，分块
        边界不作承诺，拼起来的内容必须一致。顺树按叶子吐块，不拼整段。"""
        end = self._check_range(start, end)
        return self._chunks(start, end)

    def _chunks(self, start, end):
        """顺着树按叶子吐块，不拼整段；整片叶子直接原对象交出去，不抄。"""
        remaining = end - start
        for leaf, offset in self._leaf_stream(start):
            if remaining <= 0:
                break
            piece = leaf.text[offset:offset + remaining]
            yield piece
            remaining -= len(piece)

    def _leaf_stream(self, pos):
        """从 pos 所在的叶子起按文档序逐个吐 (leaf, 叶内偏移)，显式栈。"""
        stack = []
        node = self._root
        while node is not None:
            while isinstance(node, Branch):
                if pos < node.left.length:
                    stack.append((node, False))
                    node = node.left
                else:
                    pos -= node.left.length
                    stack.append((node, True))
                    node = node.right
            yield node, pos
            pos = 0
            node = None
            while stack:
                parent, went_right = stack.pop()
                if not went_right:
                    node = parent.right
                    break

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
