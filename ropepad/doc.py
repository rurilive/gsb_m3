"""TextDoc：拿一整条 str 存正文的朴素文本缓冲。

每次插入或删除都用切片重新拼一遍整串，单次编辑的拷贝量等于正文长度，
正文涨到几十 MB 以后一步一卡。rope.py 里的 Rope 是准备顶掉它的结构，
两边接口故意做成一套，验收时同一段编辑序列分别喂进去，逐字符对拍。
位置一律是字符下标（不是字节下标，多字节字符算一个位置）。
"""

from ropepad.errors import RangeError

CHUNK = 512
"""iter_range 每次吐出的字符数上限。分块边界不作承诺，拼起来的内容才是契约。"""


class TextDoc:
    """整串实现的文本缓冲。"""

    def __init__(self, text=""):
        if not isinstance(text, str):
            raise TypeError("正文必须是 str")
        self._text = text
        self._copied = 0

    def __len__(self):
        return len(self._text)

    def text(self):
        """物化整段正文。验收和调试用，编辑路径不该调。"""
        return self._text

    def stats(self):
        """length 正文字符数；copied 是本对象诞生以来构造与编辑真正新写出来的字符数
        （源对象的历史不继承），整串实现里它随正文长度涨。"""
        return {"length": len(self._text), "copied": self._copied}

    def slice(self, start, end):
        """取 [start, end) 做成新的 TextDoc，本对象不动。

        必须 0 <= start <= end <= 长度，否则 RangeError；副本与本体各自独立。
        """
        self._check_span(start, end)
        piece = self._text[start:end]
        doc = TextDoc(piece)
        doc._copied = len(piece)
        return doc

    def concat(self, other):
        """接在 other 后面，返回新的 TextDoc。"""
        if not isinstance(other, TextDoc):
            raise TypeError("只能和 TextDoc 拼接")
        doc = TextDoc(self._text + other.text())
        doc._copied = len(doc._text)
        return doc

    def insert(self, pos, text):
        """在 pos 处插入 text。pos 取 0 到长度（含）之外都抛 RangeError。"""
        if not isinstance(text, str):
            raise TypeError("插入的内容必须是 str")
        if pos < 0 or pos > len(self._text):
            raise RangeError("插入位置越界: %d" % pos)
        if not text:
            return
        self._text = self._text[:pos] + text + self._text[pos:]
        self._copied += len(self._text)

    def delete(self, start, count):
        """删掉 [start, start+count) 这段。count 为 0 是空操作，什么都不动。"""
        n = len(self._text)
        if count < 0 or start < 0 or start + count > n:
            raise RangeError("删除区间越界: %s" % ((start, count),))
        if count == 0:
            return
        self._text = self._text[:start] + self._text[start + count:]
        self._copied += len(self._text)

    def iter_range(self, start, end):
        """按块迭代 [start, end) 的正文，每块一个 str，块长不超过 CHUNK。

        start 负数或者超过长度抛 RangeError，end 小于 start 也抛，end 超过长度
        就截到末尾（方便从某处一路扫到文末，这点和 slice 不同）；参数在取迭代器
        时当场校验，不是等第一次 next 才炸。分块边界和别的实现不作承诺。
        """
        end = self._check_range(start, end)
        return self._chunks(start, end)

    def _chunks(self, start, end):
        text = self._text[start:end]
        for i in range(0, len(text), CHUNK):
            yield text[i:i + CHUNK]

    def _check_span(self, start, end):
        n = len(self._text)
        if start < 0 or end < 0 or start > end or end > n:
            raise RangeError("区间越界: %s，正文长度 %d" % ((start, end), n))

    def _check_range(self, start, end):
        n = len(self._text)
        if start < 0 or start > n or end < start:
            raise RangeError("区间越界: %s，正文长度 %d" % ((start, end), n))
        return min(end, n)
