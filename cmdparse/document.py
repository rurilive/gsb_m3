"""命令流文档：面板粘进来的一整块多行命令流。

切行口径刻意简单：按 "\\n" 切开，行号 1 起算。末尾那个换行会切出一个
空行，所以 "ls\\n" 是 2 行；面板宁可多算一行，也不做特判。

整块内容在进面板时先过一道 NUL 检查：粘贴事故经常把二进制片段带进来，
这种内容直接拒收，并用 diagnostics 的坐标口径报出它是第几行第几列。
"""

from cmdparse.diagnostics import ParseError
from cmdparse.lexer import tokenize
from cmdparse.tokenizer import split_words


class CommandDocument:
    """一整块命令流，支持切行、逐行分词与统计。"""

    def __init__(self, text):
        if not isinstance(text, str):
            raise TypeError("命令流必须是 str，收到 {}".format(type(text).__name__))
        nul_at = text.find("\x00")
        if nul_at != -1:
            line, column = _locate(text, nul_at)
            raise ParseError(
                "命令流里混进了 NUL 字节，先清掉再贴",
                line=line,
                column=column,
                source_line=text.split("\n")[line - 1],
            )
        self._text = text
        self._lines = text.split("\n")
        self._token_cache = None

    def line_count(self):
        """切出来的行数。"""
        return len(self._lines)

    def line(self, number):
        """按行号取原文，越界抛 IndexError。"""
        if not isinstance(number, int) or isinstance(number, bool):
            raise TypeError("行号得是 int")
        if number < 1 or number > len(self._lines):
            raise IndexError("行号 {} 越界，一共 {} 行".format(number, len(self._lines)))
        return self._lines[number - 1]

    def iter_lines(self):
        """逐行给 (行号, 文本)，行号 1 起算。"""
        for number, text in enumerate(self._lines, 1):
            yield number, text

    def commands(self):
        """逐行切词，空行跳过；返回 (行号, 词列表) 的列表。"""
        result = []
        for number, text in self.iter_lines():
            words = split_words(text)
            if words:
                result.append((number, words))
        return result

    def tokens(self):
        """走新词法逐行给词素，空行跳过；返回 (行号, Token 列表) 的列表。

        与 :meth:`commands` 不同，这里在整块文本上跑一遍
        :func:`cmdparse.lexer.tokenize`，所以行尾续行、跨行引号都认得；
        跨了行的词素归在它起点所在的那一行。词法失败时原样抛
        :class:`ParseError`，行列指回整块文档。
        """
        if self._token_cache is None:
            grouped = {}
            order = []
            for token in tokenize(self._text):
                if token.start_line not in grouped:
                    grouped[token.start_line] = []
                    order.append(token.start_line)
                grouped[token.start_line].append(token)
            self._token_cache = [
                (number, grouped[number]) for number in order
            ]
        return self._token_cache

    def word_count(self):
        """全篇词数，空行不计。"""
        return sum(len(words) for _, words in self.commands())


def _locate(text, index):
    """把字符下标换成 (行, 列)，都从 1 起算。"""
    prefix = text[:index]
    last_break = prefix.rfind("\n")
    line = prefix.count("\n") + 1
    column = index - last_break
    return line, column
