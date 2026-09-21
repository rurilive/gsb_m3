"""新词法：按 shell（POSIX sh）常理把命令流切成带原文坐标的词素。

老的 tokenizer.split_words 只按空白硬切，引号、反斜杠全是普通字符，
所以 echo "a b" 会被拆散、未闭合引号也照样放行。这里另起一版手写词法，
标准库 shlex 的 posix 口径只当对拍参照，不依赖它出词。

规则（无引号 / 单引号 / 双引号三段状态机）：
  - 空白只认空格、制表、回车、换行四个 ASCII 空白（与 shlex 默认一致）；
    连续空白折成一个分隔符
  - 单引号里一切原样，反斜杠也不转义，换行会留在词里
  - 双引号里反斜杠只对 "、\\ 有意义；其余（含 $、`）原样保留，
    所以变量占位符 "$GREETING" 会完整活下去
  - 无引号时反斜杠转义下一个字符（吃掉反斜杠）
  - 无引号处行尾的 "\\" + 换行做续行：反斜杠与换行都删掉，词不断开
  - "#" 只在词首（行首或空白后）起注释，注释到行尾；词中的 # 是普通
    字符（这一点与 shlex 不同，shlex 会把词中 # 之后整段当注释）
  - 空引号 ''、"" 也是词，吐一个空串词素

每个词素（Token）带解码后的 text、原文起止行列（1 起算、末尾开区间）、
绝对码点下标，以及分段信息（Segment：普通段/单引段/双引段），面板高亮
直接拿区间在原文上切片即可。坐标按需定位（访问 start/end 时才换算
行列），扫描过程只做一次线性正则推进，能吃下几十兆命令流。

未闭合引号、悬空转义抛 diagnostics.ParseError，行列指到出错的源头
字符（引号指开引号、转义指反斜杠）。

入参喂 str，或 bytes/bytearray/bytes 视图（按 UTF-8 用 surrogateescape
解码，乱码原样当字符，绝不崩、绝不卡死）；其余类型抛 TypeError。
"""

import bisect
import re

from cmdparse.diagnostics import ParseError


class Position(tuple):
    """源坐标：(line, column, offset)，行列 1 起算、offset 为 0 起码点下标。"""

    __slots__ = ()

    def __new__(cls, line, column, offset):
        return tuple.__new__(cls, (line, column, offset))

    @property
    def line(self):
        return self[0]

    @property
    def column(self):
        return self[1]

    @property
    def offset(self):
        return self[2]


class Segment(tuple):
    """词素内一段：(kind, text, start, end)。

    kind 取 "plain"、"single"、"double"；text 是该段解码后的内容
    （引号字符本身不在内，转义已按段规则处理）；start/end 是该段在
    原文上的区间（末尾开）：普通段连同反斜杠一起罩住，引用段连同引号
    一起罩住。底层只存 offset，start/end 访问时才换算行列，大语料下
    不会为没人看的坐标白建对象。
    """

    __slots__ = ()

    def __new__(cls, kind, text, start_offset, end_offset, line_breaks):
        return tuple.__new__(cls, (kind, text, start_offset, end_offset,
                                   line_breaks))

    @property
    def kind(self):
        return self[0]

    @property
    def text(self):
        return self[1]

    @property
    def start(self):
        return _locate(self[4], self[2])

    @property
    def end(self):
        return _locate(self[4], self[3])

    @property
    def start_offset(self):
        return self[2]

    @property
    def end_offset(self):
        return self[3]

    def __eq__(self, other):
        if not isinstance(other, Segment):
            return NotImplemented
        return (self.kind == other.kind and self.text == other.text
                and self[2] == other[2] and self[3] == other[3])


class Token:
    """一个词素：解码文本、整词原文区间、分段明细。"""

    __slots__ = ("text", "start_offset", "end_offset", "_raw_segments",
                 "_segments_view", "_line_breaks")

    def __init__(self, text, start_offset, end_offset, raw_segments,
                 line_breaks):
        self.text = text
        self.start_offset = start_offset
        self.end_offset = end_offset
        self._raw_segments = raw_segments
        self._line_breaks = line_breaks

    def locate(self, offset):
        """把绝对码点下标换成 Position（行列 1 起算、末尾开口径）。"""
        return _locate(self._line_breaks, offset)

    @property
    def start(self):
        return self.locate(self.start_offset)

    @property
    def end(self):
        return self.locate(self.end_offset)

    @property
    def segments(self):
        built = getattr(self, "_segments_view", None)
        if built is None:
            built = tuple(
                Segment(kind, segment_text, start_offset, end_offset,
                        self._line_breaks)
                for kind, segment_text, start_offset, end_offset
                in self._raw_segments)
            self._segments_view = built
        return built

    def __eq__(self, other):
        if not isinstance(other, Token):
            return NotImplemented
        return (self.text == other.text
                and self.start_offset == other.start_offset
                and self.end_offset == other.end_offset
                and self.segments == other.segments)

    def __repr__(self):
        start = self.start
        end = self.end
        return "Token({!r}, start={}, end={})".format(
            self.text, tuple(start), tuple(end))


_WHITESPACE = frozenset(" \t\r\n")
_WHITESPACE_RUN = re.compile(r"[ \t\r\n]+")
_COMMENT_RUN = re.compile(r"#[^\n]*")
_PLAIN_RUN = re.compile(r'[^ \t\r\n\'"\\#]+')
_DOUBLE_RUN = re.compile(r'[^"\\]+')


def tokenize(text):
    """把一整段命令流词法切成 Token 列表（按出现顺序）。

    接受 str，或 bytes/bytearray/bytes 视图（UTF-8 + surrogateescape
    解码）；非法类型抛 TypeError；未闭合引号或悬空转义抛 ParseError。
    """
    text = _decode(text)
    line_breaks = [match.start() for match in re.finditer(r"\n", text)]

    tokens = []
    parts = []
    segments = []
    chunks = []

    in_word = False
    word_start = 0
    chunk_start = 0

    index = 0
    length = len(text)

    def make_position(offset):
        return _locate(line_breaks, offset)

    def raise_at(offset, message):
        raise _error(message, make_position(offset), text)

    while index < length:
        char = text[index]

        if not in_word:
            if char in _WHITESPACE:
                index = _WHITESPACE_RUN.match(text, index).end()
                continue
            if char == "#":
                index = _COMMENT_RUN.match(text, index).end()
                continue
            if char == "\\":
                if index + 1 >= length:
                    raise_at(index, "行尾是个孤零零的反斜杠，后面没字符可转义")
                if text[index + 1] == "\n":
                    index += 2
                    continue
                in_word = True
                word_start = chunk_start = index
                chunks.append(text[index + 1])
                index += 2
                continue
            if char == "'":
                in_word = True
                word_start = index
                close = text.find("'", index + 1)
                if close == -1:
                    raise_at(index, "单引号没闭合")
                quoted = text[index + 1:close]
                parts.append(quoted)
                segments.append(("single", quoted, index, close + 1))
                index = close + 1
                continue
            if char == '"':
                in_word = True
                word_start = index
                end, quoted, bad_offset = _scan_double(text, index + 1)
                if bad_offset is not None:
                    raise_at(bad_offset,
                             "双引号里行尾的反斜杠没有可转义的字符")
                if quoted is None:
                    raise_at(index, "双引号没闭合")
                parts.append(quoted)
                segments.append(("double", quoted, index, end))
                index = end
                continue
            in_word = True
            word_start = chunk_start = index
            match = _PLAIN_RUN.match(text, index)
            chunks.append(match.group(0))
            index = match.end()
            continue

        if char in _WHITESPACE:
            if chunks:
                segment_text = "".join(chunks)
                chunks.clear()
                parts.append(segment_text)
                segments.append(("plain", segment_text, chunk_start, index))
            token_text = parts[0] if len(parts) == 1 else "".join(parts)
            tokens.append(Token(token_text, word_start, index,
                                tuple(segments), line_breaks))
            parts.clear()
            segments.clear()
            in_word = False
            index = _WHITESPACE_RUN.match(text, index).end()
            continue
        if char == "\\":
            if index + 1 >= length:
                raise_at(index, "行尾是个孤零零的反斜杠，后面没字符可转义")
            if text[index + 1] == "\n":
                if not chunks:
                    chunk_start = index
                index += 2
                continue
            if not chunks:
                chunk_start = index
            chunks.append(text[index + 1])
            index += 2
            continue
        if char == "'":
            if chunks:
                segment_text = "".join(chunks)
                chunks.clear()
                parts.append(segment_text)
                segments.append(("plain", segment_text, chunk_start, index))
            close = text.find("'", index + 1)
            if close == -1:
                raise_at(index, "单引号没闭合")
            quoted = text[index + 1:close]
            parts.append(quoted)
            segments.append(("single", quoted, index, close + 1))
            index = close + 1
            continue
        if char == '"':
            if chunks:
                segment_text = "".join(chunks)
                chunks.clear()
                parts.append(segment_text)
                segments.append(("plain", segment_text, chunk_start, index))
            end, quoted, bad_offset = _scan_double(text, index + 1)
            if bad_offset is not None:
                raise_at(bad_offset,
                         "双引号里行尾的反斜杠没有可转义的字符")
            if quoted is None:
                raise_at(index, "双引号没闭合")
            parts.append(quoted)
            segments.append(("double", quoted, index, end))
            index = end
            continue

        if char == "#":
            # 词中 # 是普通字符（shell 常理；shlex 在此会开始注释）。
            if not chunks:
                chunk_start = index
            chunks.append(char)
            index += 1
            continue
        if not chunks:
            chunk_start = index
        match = _PLAIN_RUN.match(text, index)
        chunks.append(match.group(0))
        index = match.end()

    if in_word:
        if chunks:
            segment_text = "".join(chunks)
            chunks.clear()
            parts.append(segment_text)
            segments.append(("plain", segment_text, chunk_start, length))
        token_text = parts[0] if len(parts) == 1 else "".join(parts)
        tokens.append(Token(token_text, word_start, length,
                            tuple(segments), line_breaks))
    return tokens


def _scan_double(text, index):
    """扫双引号内部，index 指向开引号后一个字符。

    成功返回 (闭引号后下标, 内容, None)；未闭合返回 (下标, None, None)；
    悬空转义返回 (下标, None, 反斜杠下标)。反斜杠只转义 "、\\，其余
    （$、`、!、换行……）连同反斜杠原样保留，与 shlex 的 posix 口径一致。
    """
    chunks = []
    length = len(text)
    while index < length:
        char = text[index]
        if char == '"':
            return index + 1, "".join(chunks), None
        if char == "\\":
            if index + 1 >= length:
                return index, None, index
            nxt = text[index + 1]
            if nxt == '"' or nxt == "\\":
                chunks.append(nxt)
                index += 2
                continue
            chunks.append("\\")
            index += 1
            continue
        match = _DOUBLE_RUN.match(text, index)
        chunks.append(match.group(0))
        index = match.end()
    return index, None, None


def _locate(line_breaks, offset):
    """把绝对码点下标换成 Position（行列 1 起算、末尾开口径）。"""
    row = bisect.bisect_right(line_breaks, offset - 1)
    column = offset + 1 if row == 0 else offset - line_breaks[row - 1]
    return Position(row + 1, column, offset)


def _error(message, position, text):
    source_line = text.split("\n")[position.line - 1]
    return ParseError(message, line=position.line, column=position.column,
                      source_line=source_line)


def _decode(text):
    if isinstance(text, str):
        return text
    if isinstance(text, (bytes, bytearray)):
        return bytes(text).decode("utf-8", "surrogateescape")
    if (isinstance(text, memoryview)
            and text.itemsize == 1 and text.format == "B"):
        return text.tobytes().decode("utf-8", "surrogateescape")
    raise TypeError(
        "待词法分析的内容必须是 str 或 bytes，收到 {}".format(type(text).__name__))
