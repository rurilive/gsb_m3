"""packwire 的编解码入口。

当前支持 int、str、list 三种值，可任意嵌套；布尔按整数处理。
线格式的字节布局见 framing 模块。解码结果一律是普通的
int / str / list，不会包成别的类型。
"""

from packwire import framing
from packwire.errors import DecodeError, EncodeError


def encode(obj):
    """把 obj 编成字节串，不支持的形态报 EncodeError。"""
    if isinstance(obj, bool):
        obj = int(obj)
    if isinstance(obj, int):
        return framing.pack_tag(framing.TAG_INT) + framing.pack_int(obj)
    if isinstance(obj, str):
        payload = _text_payload(obj)
        return (framing.pack_tag(framing.TAG_TEXT)
                + framing.pack_count(len(payload)) + payload)
    if isinstance(obj, list):
        body = b"".join(encode(item) for item in obj)
        return (framing.pack_tag(framing.TAG_ARRAY)
                + framing.pack_count(len(obj)) + body)
    raise EncodeError("unsupported type: %s" % type(obj).__name__)


def decode(data):
    """把字节串解成对象。

    多余的尾部字节、中途截断、认不出的类型码、坏 UTF-8 都报
    DecodeError 并带 offset。
    """
    if isinstance(data, bytearray):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise TypeError("decode expects bytes, got %s" % type(data).__name__)
    value, pos = _decode(data, 0)
    if pos != len(data):
        raise DecodeError("trailing bytes", pos)
    return value


def _text_payload(text):
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError:
        raise EncodeError("text is not encodable")


def _decode(data, pos):
    tag, pos = framing.read_tag(data, pos)
    if tag == framing.TAG_INT:
        return framing.read_int(data, pos)
    if tag == framing.TAG_TEXT:
        return _decode_text(data, pos)
    if tag == framing.TAG_ARRAY:
        return _decode_array(data, pos)
    raise DecodeError("unknown type code: %d" % tag, pos - 1)


def _decode_text(data, pos):
    length, pos = framing.read_count(data, pos)
    end = framing.require(data, pos, length)
    try:
        text = data[pos:end].decode("utf-8")
    except UnicodeDecodeError:
        raise DecodeError("invalid utf-8", pos)
    return text, end


def _decode_array(data, pos):
    count, pos = framing.read_count(data, pos)
    items = []
    for _ in range(count):
        item, pos = _decode(data, pos)
        items.append(item)
    return items, pos
