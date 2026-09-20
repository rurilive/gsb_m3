"""httpparse.message：HTTP/1.1 请求消息组装层。

在 LineTokenizer 吐出的行/字节之上做语义组装：请求行 -> 头部 ->
body（Content-Length / chunked）-> trailer。显式状态机，每来一段数据
推进一次，凑不够就停下等下一段——这就是流式解析的接入点。

只做语义和状态推进，不碰 \\n 扫描与行长限制（那些归 tokenizer）。
错误类型与文本与旧的单函数实现逐字一致（下游日志在正则匹配）。
"""

from httpparse import constants as C
from httpparse.tokenizer import LineTokenizer


# 组装状态：请求行 / 头部 / 定长 body / chunk 各阶段 / trailer / 完成
S_REQUEST_LINE = "REQUEST_LINE"
S_HEADERS = "HEADERS"
S_BODY_LENGTH = "BODY_LENGTH"
S_CHUNK_SIZE = "CHUNK_SIZE"
S_CHUNK_DATA = "CHUNK_DATA"
S_CHUNK_END = "CHUNK_END"
S_TRAILERS = "TRAILERS"
S_DONE = "DONE"


class RequestAssembler(object):
    """分段推进的请求组装器。

    feed(data) 追加一段字节并尽量推进；finish() 声明数据已全部到齐，
    做 EOF 收尾并返回组装好的 HttpRequest。
    一次性解析（旧 parse_request）= feed(全部) + finish()。
    """

    def __init__(self):
        from httpparse.parser import HttpRequest

        self.req = HttpRequest()
        self.tok = LineTokenizer()
        self.state = S_REQUEST_LINE
        self._prev_key = None
        self._remaining = None   # 定长 body 还差多少字节
        self._chunk_size = None  # 当前 chunk 还剩多少字节
        self._chunk_buf = bytearray()

    # ---- 对外的两个推进入口 ----

    def feed(self, data):
        self.tok.feed(data)
        self._pump()

    def finish(self):
        self._pump()
        if self.state == S_REQUEST_LINE or self.state == S_HEADERS:
            pending = self.tok.pending_size()
            if pending > C.MAX_LINE_LENGTH:
                self._error("line too long: %d bytes" % pending)
            self._error("truncated headers")
        if self.state == S_BODY_LENGTH:
            self._error(
                "truncated body: want %d, got %d"
                % (self._remaining, self.tok.available())
            )
        if self.state == S_CHUNK_SIZE:
            self._error("truncated chunk")
        if self.state == S_CHUNK_DATA:
            self._error(
                "truncated chunk: want %d, got %d"
                % (self._chunk_size, self.tok.available())
            )
        if self.state == S_CHUNK_END:
            self._error("bad chunk terminator: %r" % self.tok.peek(2))
        # S_TRAILERS / S_DONE：最后一块后 EOF 也能收尾（历史容错）
        return self.req

    # ---- 状态推进主循环 ----

    def _pump(self):
        while self.state != S_DONE:
            if self.state == S_REQUEST_LINE:
                if not self._read_request_line():
                    return
            elif self.state == S_HEADERS:
                if not self._read_headers():
                    return
            elif self.state == S_BODY_LENGTH:
                if not self._read_fixed_body():
                    return
            elif self.state == S_CHUNK_SIZE:
                if not self._read_chunk_size():
                    return
            elif self.state == S_CHUNK_DATA:
                if not self._read_chunk_data():
                    return
            elif self.state == S_CHUNK_END:
                if not self._read_chunk_end():
                    return
            elif self.state == S_TRAILERS:
                if not self._read_trailers():
                    return

    # ---- 第一段：请求行 ----

    def _read_request_line(self):
        line = self.tok.next_line()
        if line is None:
            return False
        sp1 = line.find(C.SPACE_BYTES)
        if sp1 == -1:
            self._bad_request_line(line)
        sp2 = line.find(C.SPACE_BYTES, sp1 + 1)
        if sp2 == -1:
            self._bad_request_line(line)
        if line.find(C.SPACE_BYTES, sp2 + 1) != -1:
            self._bad_request_line(line)
        method = line[0:sp1]
        target = line[sp1 + 1:sp2]
        version = line[sp2 + 1:]
        if len(method) == 0 or len(target) == 0:
            self._bad_request_line(line)
        # method 只收大写字母和连字符（历史校验，M-SEARCH 这类）
        method_ok = True
        for ch in method:
            if not (C.METHOD_MIN <= ch <= C.METHOD_MAX or ch == C.METHOD_HYPHEN):
                method_ok = False
                break
        if not method_ok:
            self._bad_request_line(line)
        # version 必须 HTTP/主.次，主次都是数字
        if not version.startswith(C.HTTP_PREFIX):
            self._bad_request_line(line)
        dot = version.find(C.DOT)
        if dot == -1:
            self._bad_request_line(line)
        try:
            int(version[len(C.HTTP_PREFIX):dot])
            int(version[dot + 1:])
        except ValueError:
            self._bad_request_line(line)
        self.req.method = method.decode("latin-1")
        self.req.target = target.decode("latin-1")
        self.req.version = version.decode("latin-1")
        self.state = S_HEADERS
        return True

    # ---- 第二段：头部 ----

    def _read_headers(self):
        while True:
            line = self.tok.next_line()
            if line is None:
                return False
            if len(line) == 0:
                # 空行，头块结束
                self._start_body()
                return True
            if line[0] in C.BLANK:
                # obs-fold：折行续上一条头的值（历史容错）
                if self._prev_key is None:
                    self._error("malformed header line: %r" % (line,))
                folded = line.strip()
                name, old_value = self.req.headers[-1]
                self.req.headers[-1] = (
                    name,
                    old_value + " " + folded.decode("latin-1"),
                )
                continue
            ci = line.find(b":")
            if ci == -1:
                self._error("malformed header line: %r" % (line,))
            name = line[0:ci]
            value = line[ci + 1:]
            # 手工去掉值两端的空白（空格 / tab）
            vs = 0
            while vs < len(value) and value[vs] in C.BLANK:
                vs += 1
            ve = len(value)
            while ve > vs and value[ve - 1] in C.BLANK:
                ve -= 1
            value = value[vs:ve]
            if len(name) == 0:
                self._error("malformed header line: %r" % (line,))
            # 值里不允许控制字符，tab 除外（历史校验）
            for ch in value:
                if ch < C.SPACE and ch != C.HTAB:
                    self._error("malformed header line: %r" % (line,))
            name_s = name.decode("latin-1")
            value_s = value.decode("latin-1")
            self.req.headers.append((name_s, value_s))
            self._prev_key = name_s

    def _start_body(self):
        # 先找 Content-Length，再找 Transfer-Encoding（历史就这两趟）
        content_length = None
        for name, value in self.req.headers:
            if content_length is None and name.lower() == C.CONTENT_LENGTH:
                try:
                    content_length = int(value.strip())
                except ValueError:
                    self._error("invalid content-length: %r" % (value,))
                if content_length < 0:
                    self._error("invalid content-length: %r" % (value,))
        transfer_enc = None
        for name, value in self.req.headers:
            if transfer_enc is None and name.lower() == C.TRANSFER_ENCODING:
                transfer_enc = value

        if transfer_enc is not None:
            if transfer_enc.strip().lower() != C.CHUNKED:
                self._error(
                    "unsupported transfer-encoding: %s" % transfer_enc.strip()
                )
            # chunked 优先，Content-Length 忽略（历史行为）
            self.state = S_CHUNK_SIZE
        elif content_length is not None:
            self._remaining = content_length
            self.state = S_BODY_LENGTH
        else:
            # 没有 CL 也没有 TE：body 为空，剩余字节忽略（历史容错）
            self.req.body = b""
            self.state = S_DONE

    # ---- 第三段 a：定长 body ----

    def _read_fixed_body(self):
        if self.tok.available() < self._remaining:
            return False
        self.req.body = self.tok.take(self._remaining)
        # body 之后的剩余字节忽略（历史容错）
        self.state = S_DONE
        return True

    # ---- 第三段 b：chunked body ----

    def _read_chunk_size(self):
        line = self.tok.next_line()
        if line is None:
            return False
        semi = line.find(C.CHUNK_EXT_SEMI)
        size_tok = line[0:semi] if semi != -1 else line
        size_tok = size_tok.strip(C.OWS_BYTES)
        try:
            size = int(size_tok, 16)
        except ValueError:
            self._error("bad chunk size: %r" % (size_tok,))
        if size < 0:
            self._error("bad chunk size: %r" % (size_tok,))
        if size == 0:
            # 最后一块，后面是 trailer 区（收下不用，EOF 也能忍）
            self.req.body = bytes(self._chunk_buf)
            self.state = S_TRAILERS
        else:
            self._chunk_size = size
            self.state = S_CHUNK_DATA
        return True

    def _read_chunk_data(self):
        if self.tok.available() < self._chunk_size:
            return False
        self._chunk_buf += self.tok.take(self._chunk_size)
        self.state = S_CHUNK_END
        return True

    def _read_chunk_end(self):
        head = self.tok.peek(2)
        if head.startswith(C.CRLF):
            self.tok.take(2)
        elif head.startswith(C.LF_BYTES):
            self.tok.take(1)
        elif len(head) >= 1 and not head.startswith(C.CR_BYTES):
            self._error("bad chunk terminator: %r" % head)
        else:
            # 只看到一个 CR，可能是 \r\n 的前半截，等下一段
            return False
        self.state = S_CHUNK_SIZE
        return True

    def _read_trailers(self):
        while True:
            if self.tok.available() == 0:
                return False
            line = self.tok.next_line(limit=None)
            if line is None:
                return False
            if len(line) == 0:
                self.state = S_DONE
                return True
            # trailer 收下但不用、不进 headers

    # ---- 错误辅助 ----

    def _bad_request_line(self, line):
        self._error("malformed request line: %r" % (line,))

    def _error(self, message):
        from httpparse.parser import ParseError

        raise ParseError(message)
