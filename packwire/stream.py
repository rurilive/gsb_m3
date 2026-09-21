"""增量解码器：按块喂入字节流，偏移按整个流计。

StreamDecoder 用显式的容器栈推进，不用递归，深嵌套不会爆栈；
长度头只用来判断数据是否到齐，绝不按声明长度预先分配。任意切分
的喂法与一次性 decode 的结果、错误和偏移完全一致。
"""

import struct

from packwire import framing
from packwire.errors import DecodeError


class _NeedMoreData(Exception):
    """内部信号：缓冲区数据不够，等下一块。"""


_PUSHED = object()


class _Frame:
    """一个未闭合的容器：数组或字段表。"""

    __slots__ = ("is_map", "remaining", "items", "pending_key", "last_key_raw")

    def __init__(self, major, count):
        self.is_map = major == framing.MAJOR_MAP
        self.remaining = count
        self.items = {} if self.is_map else []
        self.pending_key = None
        self.last_key_raw = None

    @property
    def complete(self):
        return self.remaining == 0

    @property
    def expecting_key(self):
        return self.is_map and self.remaining > 0 and self.pending_key is None


class StreamDecoder:
    """把任意切分的字节块解成一个对象，语义与一次性 decode 一致。

    feed 喂入下一块（bytes / bytearray / memoryview），finish 收尾并
    返回解出的对象。所有 DecodeError 的 offset 都按整个流计。一旦
    抛出 DecodeError，解码器即失效，不应再继续喂。
    """

    def __init__(self):
        self._buffer = bytearray()
        self._base = 0  # buffer[0] 在整个流里的偏移
        self._frames = []
        self._done = False
        self._value = None
        self._finished = False

    def feed(self, chunk):
        """喂入下一块字节，块可以任意切分。"""
        if isinstance(chunk, (bytearray, memoryview)):
            chunk = bytes(chunk)
        if not isinstance(chunk, bytes):
            raise TypeError("feed expects bytes, got %s" % type(chunk).__name__)
        if self._finished:
            raise DecodeError("feed after finish", self._base + len(self._buffer))
        self._buffer += chunk
        self._pump()

    def finish(self):
        """收尾：数据不齐按截断报错，齐了返回解出的对象。"""
        if self._finished:
            if self._done:
                return self._value
            raise DecodeError("truncated input", self._base + len(self._buffer))
        self._finished = True
        self._pump()
        if not self._done:
            raise DecodeError("truncated input", self._base + len(self._buffer))
        return self._value

    def _pump(self):
        while not self._done:
            if self._frames and self._frames[-1].complete:
                self._close_top()
                continue
            try:
                self._parse_one()
            except _NeedMoreData:
                break
        if self._done and self._buffer:
            raise DecodeError("trailing bytes", self._base)

    def _close_top(self):
        frame = self._frames.pop()
        if self._frames:
            self._attach(frame.items)
        else:
            self._value = frame.items
            self._done = True

    def _attach(self, value):
        frame = self._frames[-1]
        if frame.is_map:
            frame.items[frame.pending_key] = value
            frame.pending_key = None
        else:
            frame.items.append(value)
        frame.remaining -= 1

    def _parse_one(self):
        if not self._buffer:
            raise _NeedMoreData
        frame = self._frames[-1] if self._frames else None
        if frame is not None and frame.expecting_key:
            self._read_key(frame)
            return
        value = self._read_value()
        if value is _PUSHED:
            return
        if frame is None:
            self._value = value
            self._done = True
        else:
            self._attach(value)

    def _read_value(self):
        if len(self._frames) + 1 > framing.MAX_DEPTH:
            raise DecodeError("nesting too deep", self._base)
        initial = self._buffer[0]
        if initial in framing.FLOAT_TAGS:
            return self._read_float()
        if initial >> 5 > framing.MAJOR_MAP:
            raise DecodeError("unknown type code: %d" % initial, self._base)
        major, argument, head_size = self._peek_head()
        if major in (framing.MAJOR_BYTES, framing.MAJOR_TEXT):
            if len(self._buffer) < head_size + argument:
                raise _NeedMoreData
            self._drop(head_size)
            payload = self._take(argument)
            if major == framing.MAJOR_BYTES:
                return payload
            try:
                return payload.decode("utf-8")
            except UnicodeDecodeError:
                raise DecodeError("invalid utf-8", self._base - argument)
        self._drop(head_size)
        if major == framing.MAJOR_UINT:
            return argument
        if major == framing.MAJOR_NEGINT:
            return -1 - argument
        self._frames.append(_Frame(major, argument))
        return _PUSHED

    def _read_key(self, frame):
        start = self._base
        if len(self._frames) + 1 > framing.MAX_DEPTH:
            raise DecodeError("nesting too deep", start)
        if self._buffer[0] >> 5 != framing.MAJOR_TEXT:
            raise DecodeError("map key is not text", start)
        _major, length, head_size = self._peek_head()
        if len(self._buffer) < head_size + length:
            raise _NeedMoreData
        self._drop(head_size)
        payload = self._take(length)
        try:
            key = payload.decode("utf-8")
        except UnicodeDecodeError:
            raise DecodeError("invalid utf-8", self._base - length)
        # 首部已校验过是最短形，重编码即原始字节
        raw = framing.pack_head(framing.MAJOR_TEXT, length) + payload
        previous = frame.last_key_raw
        if previous is not None and (len(previous), previous) >= (len(raw), raw):
            raise DecodeError("map keys out of canonical order", start)
        frame.last_key_raw = raw
        frame.pending_key = key

    def _peek_head(self):
        """读首部但不消费，返回 (主类型, 参数, 首部长度)。"""
        initial = self._buffer[0]
        info = initial & 0x1F
        if info < 24:
            return initial >> 5, info, 1
        size_info = framing.LONG_INFO.get(info)
        if size_info is None:
            raise DecodeError("unsupported additional info: %d" % info, self._base)
        size, fmt, minimum = size_info
        if len(self._buffer) < 1 + size:
            raise _NeedMoreData
        argument = struct.unpack_from(fmt, self._buffer, 1)[0]
        if argument < minimum:
            raise DecodeError("non-canonical head: not shortest form", self._base)
        return initial >> 5, argument, 1 + size

    def _drop(self, n):
        del self._buffer[:n]
        self._base += n

    def _read_float(self):
        initial = self._buffer[0]
        for tag, fmt, size in framing.FLOAT_TYPES:
            if initial == tag:
                if len(self._buffer) < 1 + size:
                    raise _NeedMoreData
                raw = bytes(self._buffer[:1 + size])
                value = struct.unpack_from(fmt, self._buffer, 1)[0]
                if framing.pack_float(value) != raw:
                    raise DecodeError("non-canonical float", self._base)
                del self._buffer[:1 + size]
                self._base += 1 + size
                return value

    def _take(self, n):
        if len(self._buffer) < n:
            raise _NeedMoreData
        payload = bytes(self._buffer[:n])
        del self._buffer[:n]
        self._base += n
        return payload
