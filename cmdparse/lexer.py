"""POSIX shell 风味的命令词法分析。

面板上一版 :mod:`cmdparse.tokenizer` 只会按空白硬切，引号里的空格、续行、
注释全不认得。这里自己写一遍词法，``shlex`` 只留作对拍参照，不参与运行时。

规则按 shell 常理：

- 单引号 ``'...'`` 内一律字面，反斜杠也不转义；
- 双引号 ``"..."`` 内 ``\\"``、``\\\\``、``\\$``、``\\` `` 照 shell 规则
  转义，其余反斜杠原样保留，``$`` 开头的变量占位符不会被吃掉；
- 词外反斜杠转义下一个任意字符（含空白）；
- 反斜杠加换行是行尾续行，引号内外都把换行消掉；
- ``#`` 只在词首（行首或紧跟空白）起注释，词内其余位置是普通字符；
- 空引号是一个活下来的空词，``a""b`` 与 ``ab`` 拼成同一个词。

与 ``shlex.split(posix=True, comments=True)`` 的差异（对拍时点名）：

1. shlex 把词外的 ``\\`` + 换行当成“转义换行”，词文本里留一个真实换行；
   shell 常理是行尾续行，换行消失。
2. shlex 双引号内只认 ``\\"`` 和 ``\\\\`` 两种转义，``"\\$x"`` 会保留
   反斜杠；shell 常理下 ``$`` 被转义成字面量。``\\` `` 同理。
3. shlex 开了注释后把词内 ``#`` 也当注释起点（``a#b`` 被注释掉）；
   shell 常理只认词首的 ``#``（``a#b`` 是一个词）。

坐标沿用 :mod:`cmdparse.diagnostics` 的口径：行列均 1 起算、按码点数，
末尾开区间。位置都指回原始输入，续行跨过的换行也包含在词素区间里。

输入收 ``str``，也收 ``bytes``：字节按 UTF-8 宽松解码（``errors="replace"``），
喂乱码只会出词素或 :class:`~cmdparse.diagnostics.ParseError`，不崩不卡。
"""

from cmdparse.diagnostics import ParseError

# 分隔符只收 ASCII 空白与换行，跟 shlex 默认 whitespace 对齐；
# 全角空格、\v、\f 在 shell/shlex 里都是普通字符。
_SEPARATORS = frozenset(" \t\r\n")

# 双引号内反斜杠认账的字符：" \ $ `（行尾续行的 \n 单独处理）。
_DOUBLE_QUOTE_ESCAPES = frozenset('"\\$`')


class Token:
    """一个词素：转义还原后的文本，加原文起止行列（1 起算、末尾开）。"""

    __slots__ = ("text", "start_line", "start_column", "end_line", "end_column")

    def __init__(self, text, start_line, start_column, end_line, end_column):
        self.text = text
        self.start_line = start_line
        self.start_column = start_column
        self.end_line = end_line
        self.end_column = end_column

    def source_slice(self, source):
        """按词素区间从原文里切出原始字符（含引号、反斜杠、续行换行）。"""
        lines = source.split("\n")
        if self.start_line == self.end_line:
            return lines[self.start_line - 1][
                self.start_column - 1:self.end_column - 1
            ]
        pieces = [lines[self.start_line - 1][self.start_column - 1:]]
        for line_number in range(self.start_line + 1, self.end_line):
            pieces.append(lines[line_number - 1])
        pieces.append(lines[self.end_line - 1][:self.end_column - 1])
        return "\n".join(pieces)

    def __eq__(self, other):
        if not isinstance(other, Token):
            return NotImplemented
        return (
            self.text == other.text
            and self.start_line == other.start_line
            and self.start_column == other.start_column
            and self.end_line == other.end_line
            and self.end_column == other.end_column
        )

    def __hash__(self):
        return hash((
            self.text,
            self.start_line,
            self.start_column,
            self.end_line,
            self.end_column,
        ))

    def __repr__(self):
        return "Token({!r}, {}:{}..{}:{})".format(
            self.text,
            self.start_line,
            self.start_column,
            self.end_line,
            self.end_column,
        )


def tokenize(text):
    """把一整块命令流切成词素列表。

    合法输入给 :class:`Token` 列表（空输入给空列表，空引号给空词）；
    未闭合引号、悬空转义抛 :class:`~cmdparse.diagnostics.ParseError`，
    坐标指回源头。``bytes`` 按 UTF-8 宽松解码，其余类型抛 ``TypeError``。
    """
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    elif not isinstance(text, str):
        raise TypeError(
            "待词法分析的内容必须是 str 或 bytes，收到 {}".format(
                type(text).__name__
            )
        )

    tokens = []
    length = len(text)
    index = 0
    line = 1
    column = 1

    def fail(message, at_line, at_column):
        raise ParseError(
            message,
            line=at_line,
            column=at_column,
            source_line=text.split("\n")[at_line - 1],
        )

    while index < length:
        char = text[index]

        if char in _SEPARATORS:
            index += 1
            if char == "\n":
                line += 1
                column = 1
            else:
                column += 1
            continue

        # 词首的 # 起行内注释（shell 只认词首的 #）。
        if char == "#":
            index += 1
            column += 1
            while index < length:
                if text[index] == "\\" and index + 1 < length \
                        and text[index + 1] == "\n":
                    # 续行把注释带过换行，注释吃到真正的行尾。
                    index += 2
                    line += 1
                    column = 1
                    continue
                comment_char = text[index]
                index += 1
                if comment_char == "\n":
                    line += 1
                    column = 1
                    break
                column += 1
            continue

        # 一个词的起点，记录开区间坐标。
        start_line = line
        start_column = column
        pieces = []
        started = False

        while index < length:
            char = text[index]
            if char in _SEPARATORS:
                break

            if char == "'":
                quote_line, quote_column = line, column
                index += 1
                column += 1
                started = True
                while True:
                    if index >= length:
                        fail("单引号没有闭合", quote_line, quote_column)
                    inner = text[index]
                    if inner == "'":
                        index += 1
                        column += 1
                        break
                    pieces.append(inner)
                    index += 1
                    if inner == "\n":
                        line += 1
                        column = 1
                    else:
                        column += 1
                continue

            if char == '"':
                quote_line, quote_column = line, column
                index += 1
                column += 1
                started = True
                while True:
                    if index >= length:
                        fail("双引号没有闭合", quote_line, quote_column)
                    inner = text[index]
                    if inner == '"':
                        index += 1
                        column += 1
                        break
                    if inner == "\\":
                        slash_line, slash_column = line, column
                        if index + 1 >= length:
                            fail(
                                "双引号里的反斜杠后面没有可转义的字符",
                                slash_line,
                                slash_column,
                            )
                        following = text[index + 1]
                        if following == "\n":
                            # 引号内续行：反斜杠与换行都不进词文本。
                            index += 2
                            line += 1
                            column = 1
                            continue
                        if following in _DOUBLE_QUOTE_ESCAPES:
                            pieces.append(following)
                        else:
                            pieces.append("\\")
                            pieces.append(following)
                        index += 2
                        column += 2
                        continue
                    pieces.append(inner)
                    index += 1
                    if inner == "\n":
                        line += 1
                        column = 1
                    else:
                        column += 1
                continue

            if char == "\\":
                slash_line, slash_column = line, column
                if index + 1 >= length:
                    fail("反斜杠后面没有可转义的字符", slash_line, slash_column)
                following = text[index + 1]
                if following == "\n":
                    # 行尾续行：反斜杠与换行都不进词文本，但留在原文区间。
                    index += 2
                    line += 1
                    column = 1
                    continue
                pieces.append(following)
                started = True
                index += 2
                column += 2
                continue

            # 词内（含引号刚闭合后）的 # 只是普通字符。
            pieces.append(char)
            started = True
            index += 1
            column += 1

        if started:
            tokens.append(Token(
                "".join(pieces), start_line, start_column, line, column,
            ))

    return tokens
