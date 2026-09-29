"""最朴素的单机字符串缓冲。

当前能力仅限于单个副本本地使用：内部就是一个 Python 字符串，
insert 按下标把新文本拼进去，delete 按下标把一段字符直接从字符串里切掉。
没有位置标识、没有并发标记、没有合并、没有因果，因此两个副本各自本地
改过之后无法把各自的操作带到一起收敛到同一段文本。
纯标准库，无外部依赖。
"""


class ColitextError(Exception):
    """缓冲使用不当或状态非法时抛出的异常基类。"""


class TextBuf:
    """仅支持本地按下标增删的基础字符串缓冲。

    内部用一个 Python 字符串保存文本。insert 在下标处插入一段文本并返回
    自身；delete 在下标处删除若干字符并返回自身；text 给出当前文本副本。
    下标越界、文本类型不对或删除数量非法时抛出 ColitextError。
    """

    def __init__(self, text=""):
        if not isinstance(text, str):
            raise ColitextError("text must be a string")
        self._text = text

    def insert(self, index, text):
        """在下标 index 处插入 text，返回自身。"""
        if not isinstance(index, int) or isinstance(index, bool):
            raise ColitextError("index must be an int")
        if not isinstance(text, str):
            raise ColitextError("text must be a string")
        if index < 0 or index > len(self._text):
            raise ColitextError("index out of range")
        self._text = self._text[:index] + text + self._text[index:]
        return self

    def delete(self, index, count=1):
        """从下标 index 起删除 count 个字符，返回自身。"""
        if not isinstance(index, int) or isinstance(index, bool):
            raise ColitextError("index must be an int")
        if not isinstance(count, int) or isinstance(count, bool):
            raise ColitextError("count must be an int")
        if count < 0:
            raise ColitextError("count must not be negative")
        if index < 0 or index + count > len(self._text):
            raise ColitextError("range out of bounds")
        self._text = self._text[:index] + self._text[index + count:]
        return self

    def text(self):
        """当前文本的副本。"""
        return self._text

    def __len__(self):
        return len(self._text)

    def __str__(self):
        return self._text

    def __repr__(self):
        return f"TextBuf({self._text!r})"
