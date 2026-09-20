"""按块喂入的 multipart/form-data 解析器。

上传网关把网络收到的字节一块块喂进来,这里负责切出表单字段和
文件内容:每个部分的头部先报给 sink,正文按到达的块写下去,部分
结束再报一次。正文不留在解析器手里,大文件可以边收边落盘。
"""

from .errors import ParseError
from .headers import parse_header_block, parse_params
from .sink import PartCollector

_PREAMBLE = 0
_HEADERS = 1
_BODY = 2
_DONE = 3


class MultipartParser:
    """按块喂入的 multipart/form-data 解析器。

    用法:

        parser = MultipartParser(boundary, sink)
        for chunk in chunks:
            parser.feed(chunk)
        parser.finish()

    sink 要有 begin_part(headers, params)、write(data)、end_part()
    三个方法,见 sink.py。分隔行按 CRLF 换行,收尾分隔行之后的
    epilogue 忽略;正文不在解析器里缓存,手里只留跨块的分隔行前缀。
    """

    def __init__(self, boundary, sink=None):
        if isinstance(boundary, str):
            boundary = boundary.encode("ascii")
        if not boundary:
            raise ValueError("boundary must not be empty")
        self._boundary = bytes(boundary)
        # 正文里的分隔行,行首那个 CRLF 也算它的
        self._marker = b"\r\n--" + self._boundary
        # 第一个分隔行前面可能没有 CRLF(前导内容为空时)
        self._opening = b"--" + self._boundary
        self._sink = sink if sink is not None else PartCollector()
        self._state = _PREAMBLE
        # 跨块没定性质的字节:正文里可能是分隔行前缀的一截,
        # 或者前导里可能是第一个分隔行前缀的一截,或者半个头块
        self._buf = b""
        # preamble 阶段还没丢过任何字节,流首可能是不带 CRLF 的开场分隔行
        self._at_start = True
        # 当前有没有还没 end_part 的部分
        self._open = False

    def feed(self, chunk):
        """喂一块字节,内容有多少就处理多少。"""
        if not chunk or self._state == _DONE:
            return
        data = self._buf + bytes(memoryview(chunk))
        self._buf = b""
        while data:
            if self._state == _PREAMBLE:
                data = self._eat_preamble(data)
            elif self._state == _HEADERS:
                data = self._eat_headers(data)
            elif self._state == _BODY:
                data = self._eat_body(data)
            else:
                return

    def finish(self):
        """流结束,收尾。结构没收完整就抛 ParseError。"""
        if self._state != _DONE:
            if self._state == _BODY:
                raise ParseError("stream ended inside a part body: "
                                 "missing closing boundary")
            if self._state == _HEADERS:
                raise ParseError("stream ended inside part headers")
            raise ParseError("stream ended before any boundary line")
        self._buf = b""

    # ---- 各状态的处理 ----

    def _eat_preamble(self, data):
        if self._at_start and data.startswith(self._opening):
            rest = data[len(self._opening):]
            if len(rest) < 2:
                # 开场分隔行的校验字节(-- 或 CRLF)还没到齐,
                # 开场整体留住,不能当成前导丢掉
                self._buf = data
                return b""
            self._at_start = False
            return self._after_opening(rest)
        search_from = 0
        while True:
            i = data.find(self._marker, search_from)
            if i < 0:
                break
            pos = i + len(self._marker)
            tail = data[pos:pos + 2]
            if len(tail) == 2:
                if tail == b"--" or tail == b"\r\n":
                    self._at_start = False
                    return self._after_marker(data[pos:])
                # 跟别的字节只是正文里长得像,不算分隔行,继续找
                search_from = i + 1
                continue
            # marker 在 data 末尾,校验字节还没到齐:前面的前导
            # 字节丢掉,marker 这一截(可能还多 1 字节)留住定性
            if i > 0:
                self._at_start = False
            self._buf = data[i:]
            return b""
        # 没拿到可用的分隔行:丢掉明确属于前导的字节,只留可能是
        # 分隔行开头的后缀;流首还要照顾不带 CRLF 的开场分隔行
        k = self._marker_prefix_len(data)
        if self._at_start:
            k = max(k, self._prefix_len(data, self._opening))
        held = data[len(data) - k:] if k else b""
        if len(held) < len(data):
            self._at_start = False
        self._buf = held
        return b""

    def _eat_headers(self, data):
        # 头部块用 CRLF CRLF 结束,和怎么切块无关
        i = data.find(b"\r\n\r\n")
        if i >= 0:
            return self._begin_part(data[:i], data[i + 4:])
        # 结束空行可能落在任意切块位置,头部整块先攒着(头部块很小)
        self._buf = data
        return b""

    def _eat_body(self, data):
        search_from = 0
        while True:
            i = data.find(self._marker, search_from)
            if i < 0:
                break
            pos = i + len(self._marker)
            tail = data[pos:pos + 2]
            if len(tail) == 2:
                # 完整分隔行,后面两字节必须是 -- 或 CRLF;
                # 跟别的字节只是正文里长得像,继续往后找
                if tail == b"--" or tail == b"\r\n":
                    self._emit(data[:i])
                    return self._after_marker(data[pos:])
                search_from = i + 1
                continue
            # marker 在 data 尾部、两字节校验符还没到:marker 之前的
            # 正文先交出去,marker 这一截留着等下一块定性
            self._emit(data[:i])
            self._buf = data[i:]
            return b""
        # 整块都没有完整 marker:把末尾可能是 marker 前缀的一截留住,
        # 其余都是正文;前缀若被下一块证伪,会原样补回 sink
        k = self._marker_prefix_len(data)
        self._emit(data[:len(data) - k] if k else data)
        self._buf = data[len(data) - k:] if k else b""
        return b""

    def _after_marker(self, rest):
        """分隔行本体之后:-- 是收尾,CRLF 表示后面还跟着一个部分。

        两个校验字节只到了 0 或 1 个时先攒着,绝不倒进头部状态。
        """
        head = rest[:2]
        if len(head) < 2:
            self._buf = rest
            return b""
        if head == b"--":
            self._end_part()
            self._state = _DONE
            # 收尾分隔行之后的 epilogue 一律忽略
            return b""
        if head == b"\r\n":
            self._end_part()
            self._state = _HEADERS
            return rest[2:]
        raise ParseError("malformed boundary line: expected '--' or CRLF")

    def _after_opening(self, rest):
        """开场分隔行(不带 CRLF 的那个)之后的处理。"""
        head = rest[:2]
        if len(head) < 2:
            self._buf = rest
            return b""
        if head == b"--":
            self._state = _DONE
            return b""
        if head == b"\r\n":
            self._state = _HEADERS
            return rest[2:]
        raise ParseError("malformed opening boundary line")

    def _emit(self, data):
        """把正文交给 sink,跳过零长度的空写。"""
        if data:
            self._sink.write(data)

    @staticmethod
    def _prefix_len(data, token):
        """data 末尾与 token 开头重合的最长后缀长度(可为整个 token)。"""
        limit = min(len(data), len(token))
        for k in range(limit, 0, -1):
            if token.startswith(data[-k:]):
                return k
        return 0

    def _marker_prefix_len(self, data):
        """data 末尾可能是正文分隔行开头的长度,行首的 CR 也算。"""
        return self._prefix_len(data, self._marker)

    def _begin_part(self, block, rest):
        headers = parse_header_block(block)
        params = parse_params(headers.get("content-disposition", ""))
        self._sink.begin_part(headers, params)
        self._open = True
        self._state = _BODY
        return rest

    def _end_part(self):
        if self._open:
            self._sink.end_part()
            self._open = False
