"""字节串切段：把缓冲按 ASCII 空白与 ASCII 标点切开。

切分口径（已由 tests 锁定，改动即破坏兼容）：

- 分隔字节：ASCII 空白（\\t \\n \\x0b \\x0c \\r 空格）与 ASCII 标点。
- 词字节：其余全部字节，含 0x80 到 0xFF。UTF-8 的多字节序列与
  CJK 标点（如中文逗号）都落在词字节一侧。
- 段：同类字节的最长连续段，分隔段与词段交替出现；相邻的分隔
  字节合成一段（如 b" , "），不会被再拆开。
- 每个字节恰好属于一个段，把段按顺序拼回即原缓冲。
"""

WHITESPACE = frozenset(b"\t\n\x0b\x0c\r ")
PUNCTUATION = frozenset(b"!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
SEPARATORS = WHITESPACE | PUNCTUATION


def is_separator(byte_value):
    """判断一个字节值（0 到 255 的 int）是否属于分隔类。"""
    if not isinstance(byte_value, int):
        raise TypeError("byte_value 必须是 int，收到 %r" % (byte_value,))
    return byte_value in SEPARATORS


def split_segments(data):
    """把 bytes 切成段列表，逐字节覆盖、顺序不变。"""
    if not isinstance(data, bytes):
        raise TypeError("split_segments 只接受 bytes，收到 %r" % (type(data).__name__,))
    if not data:
        return []
    segments = []
    start = 0
    current = data[0] in SEPARATORS
    for index in range(1, len(data)):
        flag = data[index] in SEPARATORS
        if flag != current:
            segments.append(data[start:index])
            start = index
            current = flag
    segments.append(data[start:])
    return segments


def segment_frequencies(data):
    """对切段后的结果做频次统计，返回按 (频次降序, 段字节升序) 的列表。"""
    counts = {}
    for segment in split_segments(data):
        counts[segment] = counts.get(segment, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def join_segments(segments):
    """split_segments 的逆操作，用于自检覆盖性。"""
    return b"".join(segments)
