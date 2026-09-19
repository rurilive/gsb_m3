"""文本编辑命令与缓冲。"""


class Buffer:
    """带名字的文本缓冲，key 用于区分编辑目标。"""

    def __init__(self, key, text=""):
        self.key = key
        self.text = text


class Command:
    """编辑命令基类：do() 执行，undo() 撤销。

    key 标识命令作用的缓冲，供历史层按目标分组。
    """

    key = None

    def do(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError


class InsertText(Command):
    """在 pos 处插入 text。"""

    def __init__(self, buf, pos, text):
        self.buf = buf
        self.key = buf.key
        self.pos = pos
        self.text = text

    def do(self):
        t = self.buf.text
        self.buf.text = t[:self.pos] + self.text + t[self.pos:]

    def undo(self):
        t = self.buf.text
        self.buf.text = t[:self.pos] + t[self.pos + len(self.text):]


class DeleteText(Command):
    """从 pos 起删除 length 个字符。"""

    def __init__(self, buf, pos, length):
        self.buf = buf
        self.key = buf.key
        self.pos = pos
        self.length = length
        self._removed = None

    def do(self):
        t = self.buf.text
        self._removed = t[self.pos:self.pos + self.length]
        self.buf.text = t[:self.pos] + t[self.pos + self.length:]

    def undo(self):
        t = self.buf.text
        self.buf.text = t[:self.pos] + self._removed + t[self.pos:]
