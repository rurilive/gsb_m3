"""packwire 的编解码入口。

支持 int、float、str、bytes、list、dict（字符串键），可任意嵌套；
布尔按整数处理，bytearray 按字节串处理。线格式的字节布局见 framing
模块。解码只认规范形：非最短首部、非最短浮点、字段表乱序或重键、
截断、尾部残留、嵌套过深，都报 DecodeError 并带 offset。
解码结果一律是普通的 int / float / str / bytes / list / dict。
"""

import struct

from packwire import framing
from packwire.errors import DecodeError, EncodeError


def encode(obj):
    """把 obj 编成规范形字节串，不支持的形态报 EncodeError。"""
    return _encode(obj, 1)


def decode(data):
    """把字节串解成对象，只认规范形。

    多余的尾部字节、中途截断、认不出的类型码、坏 UTF-8、非最短形、
    字段表乱序、嵌套过深都报 DecodeError 并带 offset。
    """
    if isinstance(data, bytearray):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise TypeError("decode expects bytes, got %s" % type(data).__name__)
    value, pos = _decode(data, 0, 1)
    if pos != len(data):
        raise DecodeError("trailing bytes", pos)
    return value


def _encode(obj, depth):
    if depth > framing.MAX_DEPTH:
        raise EncodeError("nesting too deep")
    if isinstance(obj, bool):
        return framing.pack_int(int(obj))
    if isinstance(obj, int):
        return framing.pack_int(obj)
    if isinstance(obj, float):
        return framing.pack_float(obj)
    if isinstance(obj, str):
        payload = _text_payload(obj)
        return framing.pack_head(framing.MAJOR_TEXT, len(payload)) + payload
    if isinstance(obj, (bytes, bytearray)):
        payload = bytes(obj)
        return framing.pack_head(framing.MAJOR_BYTES, len(payload)) + payload
    if isinstance(obj, list):
        return _encode_array(obj, depth)
    if isinstance(obj, dict):
        return _encode_map(obj, depth)
    raise EncodeError("unsupported type: %s" % type(obj).__name__)


def _encode_array(items, depth):
    body = b"".join(_encode(item, depth + 1) for item in items)
    return framing.pack_head(framing.MAJOR_ARRAY, len(items)) + body


def _encode_map(mapping, depth):
    entries = []
    for key, value in mapping.items():
        if not isinstance(key, str):
            raise EncodeError("map key is not text: %s" % type(key).__name__)
        entries.append((_encode(key, depth + 1), _encode(value, depth + 1)))
    # 规范序：先比编码后键的字节长度，再按字节序
    entries.sort(key=lambda entry: (len(entry[0]), entry[0]))
    body = b"".join(key + value for key, value in entries)
    return framing.pack_head(framing.MAJOR_MAP, len(entries)) + body


def _text_payload(text):
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError:
        raise EncodeError("text is not encodable")


def _decode(data, pos, depth):
    framing.require(data, pos, 1)
    if depth > framing.MAX_DEPTH:
        raise DecodeError("nesting too deep", pos)
    initial = data[pos]
    if initial in framing.FLOAT_TAGS:
        return _decode_float(data, pos)
    if initial >> 5 > framing.MAJOR_MAP:
        raise DecodeError("unknown type code: %d" % initial, pos)
    major, argument, pos = framing.read_head(data, pos)
    if major == framing.MAJOR_UINT:
        return argument, pos
    if major == framing.MAJOR_NEGINT:
        return -1 - argument, pos
    if major == framing.MAJOR_BYTES:
        end = framing.require(data, pos, argument)
        return data[pos:end], end
    if major == framing.MAJOR_TEXT:
        return _decode_text(data, pos, argument)
    if major == framing.MAJOR_ARRAY:
        return _decode_array(data, pos, argument, depth)
    return _decode_map(data, pos, argument, depth)


def _decode_float(data, pos):
    initial = data[pos]
    for tag, fmt, size in framing.FLOAT_TYPES:
        if initial == tag:
            end = framing.require(data, pos + 1, size)
            value = struct.unpack_from(fmt, data, pos + 1)[0]
            if framing.pack_float(value) != data[pos:end]:
                raise DecodeError("non-canonical float", pos)
            return value, end


def _decode_text(data, pos, length):
    end = framing.require(data, pos, length)
    try:
        text = data[pos:end].decode("utf-8")
    except UnicodeDecodeError:
        raise DecodeError("invalid utf-8", pos)
    return text, end


def _decode_array(data, pos, count, depth):
    items = []
    for _ in range(count):
        item, pos = _decode(data, pos, depth + 1)
        items.append(item)
    return items, pos


def _decode_map(data, pos, count, depth):
    items = {}
    previous_key = None
    for _ in range(count):
        framing.require(data, pos, 1)
        if depth + 1 > framing.MAX_DEPTH:
            raise DecodeError("nesting too deep", pos)
        if data[pos] >> 5 != framing.MAJOR_TEXT:
            raise DecodeError("map key is not text", pos)
        key_start = pos
        key, pos = _decode(data, pos, depth + 1)
        encoded_key = data[key_start:pos]
        if (previous_key is not None
                and (len(previous_key), previous_key) >= (len(encoded_key), encoded_key)):
            raise DecodeError("map keys out of canonical order", key_start)
        previous_key = encoded_key
        value, pos = _decode(data, pos, depth + 1)
        items[key] = value
    return items, pos
