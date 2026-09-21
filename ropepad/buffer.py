"""TextBuffer：编辑器会话层，正文放在 doc 里，会话自己维护命名标记和修订号。

doc 默认是 TextDoc，构造时可以用 make_doc 换成别的实现（比如 Rope.from_text），
只要它长着 text / __len__ / stats / iter_range / insert / delete 这几个口子，
标记怎么挪、修订号怎么涨，换后端前后就该一模一样。
"""

from ropepad.doc import TextDoc
from ropepad.errors import RangeError, TextError


class TextBuffer:
    """正文 + 命名标记 + 修订号。大文件扫描走 chunks，别先物化整段。"""

    def __init__(self, text="", make_doc=None):
        self._doc = (make_doc or TextDoc)(text)
        self._rev = 0
        self._marks = {}

    def __len__(self):
        return len(self._doc)

    def text(self):
        return self._doc.text()

    def chunks(self, start, end):
        """按块迭代正文区间，原样转发 doc.iter_range（校验也在那里发生）。"""
        return self._doc.iter_range(start, end)

    @property
    def revision(self):
        return self._rev

    def set_mark(self, name, pos):
        """把名字挂到 pos 上，重名的直接改挂。pos 越界抛 RangeError。"""
        if pos < 0 or pos > len(self._doc):
            raise RangeError("标记位置越界: %d" % pos)
        self._marks[name] = pos

    def mark(self, name):
        """取标记当前位置。没挂过的名字抛 TextError。"""
        if name not in self._marks:
            raise TextError("没有这个标记: %s" % name)
        return self._marks[name]

    def insert(self, pos, text):
        """插入。标记黏右：插入点不晚于标记的位置时，标记跟着右移。"""
        self._doc.insert(pos, text)
        if not text:
            return
        self._shift_right(pos, len(text))
        self._rev += 1

    def delete(self, start, count):
        """删除。落进删除区间的标记被拉到删除起点。"""
        self._doc.delete(start, count)
        if not count:
            return
        self._shift_left(start, count)
        self._rev += 1

    def replace(self, start, count, text):
        """替换，等价于先 delete(start, count) 再 insert(start, text)。

        两样都是空的就不算一次修改：正文、标记、修订号全都不动。
        """
        if not count and not text:
            return
        self._doc.delete(start, count)
        self._doc.insert(start, text)
        if count:
            self._shift_left(start, count)
        if text:
            self._shift_right(start, len(text))
        self._rev += 1

    def stats(self):
        """doc 的指标，外加一条当前修订号。"""
        s = dict(self._doc.stats())
        s["revision"] = self._rev
        return s

    def _shift_right(self, pos, size):
        for name, m in self._marks.items():
            if m >= pos:
                self._marks[name] = m + size

    def _shift_left(self, start, count):
        stop = start + count
        for name, m in self._marks.items():
            if m >= stop:
                self._marks[name] = m - count
            elif m > start:
                self._marks[name] = start
