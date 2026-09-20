"""httpparse.message：HTTP/1.1 请求组装层。

tokenizer 只给行和原始字节，这一层负责它们是什么：
请求行 -> 头部 -> body（Content-Length / chunked）的状态推进。

状态全部显式放在 RequestReader 里（替代老 parse_request 里的隐式
pos/if-elif），feed() 可以一段段喂数据，没凑够就停在当前状态等下一段；
parser.parse_request 只是把全部数据一次 feed 再 finish 的薄封装。

错误文本是契约（下游日志在正则匹配），一个字不能改。
"""

from httpparse import constants
from httpparse.tokenizer import LineTokenizer, LineTooLong


class ParseError(ValueError):
    """请求不合法。"""


class HttpRequest(object):
    def __init__(self):
        self.method = None
        self.target = None
        self.version = None
        # [(name, value)]，名字保持原始大小写、保持出现顺序，值为 latin-1 解码
        self.headers = []
        self.body = b""

    def header(self, name, default=None):
        """按名字取第一个匹配的头（大小写不敏感），没有则返回 default。"""
        want = name.lower()
        for k, v in self.headers:
            if k.lower() == want:
                return v
        return default

    def __repr__(self):
        return "HttpRequest(%r, %r, %r, %d header(s), %d body byte(s))" % (
            self.method,
            self.target,
            self.version,
            len(self.headers),
            len(self.body),
        )


# 解析状态：请求行 -> 头部 -> 按 CL 收体 / chunked 各阶段 -> 完成
_REQUEST_LINE = 1
_HEADERS = 2
_CHUNK_SIZE = 3
_CHUNK_DATA = 4
_CHUNK_TERMINATOR = 5
_CHUNK_TRAILERS = 6
_BODY_LENGTH = 7
_DONE = 8


class RequestReader(object):
    """增量请求组装器。

    用法：reader = RequestReader(); reader.feed(part) 可重复调用；
    全部数据送完后 reader.finish()。请求完整时 result 即 HttpRequest，
    否则 result 为 None（数据不够，等下一次 feed）。
    """

    def __init__(self):
        self._tokenizer = LineTokenizer()
        self.result = None
        self._req = HttpRequest()
        self._state = _REQUEST_LINE
        # 当前 chunk 数据还剩多少字节 / 尾部是否已经见过 CR
        self._chunk_remaining = 0
        self._chunk_buf = bytearray()

    def feed(self, data):
        """追加一段字节并尽量往前推进状态。"""
        self._tokenizer.feed(data)
        self._pump()
        return self.result

    def finish(self):
        """声明再无后续数据；卡在半路按历史口径报错，否则返回请求。"""
        if self._state == _DONE:
            return self.result

        if self._state == _REQUEST_LINE:
            # 无换行：超长报行长，否则是头部被截断
            pending = self._tokenizer.pending_count()
            if pending > constants.MAX_LINE_LENGTH:
                raise ParseError("line too long: %d bytes" % pending)
            raise ParseError("truncated headers")
        if self._state == _HEADERS:
            pending = self._tokenizer.pending_count()
            if pending > constants.MAX_LINE_LENGTH:
                raise ParseError("line too long: %d bytes" % pending)
            raise ParseError("truncated headers")
        if self._state == _CHUNK_SIZE:
            raise ParseError("truncated chunk")
        if self._state == _CHUNK_DATA:
            raise ParseError(
                "truncated chunk: want %d, got %d"
                % (self._chunk_remaining, self._tokenizer.pending_count())
            )
        if self._state == _CHUNK_TERMINATOR:
            # 只有一个孤立 CR 且确认无后续字节时，按旧口径报这一个字节
            if self._tokenizer.peek(2) == b"\r":
                raise ParseError("bad chunk terminator: %r" % (b"\r",))
            raise ParseError(
                "bad chunk terminator: %r" % (self._tokenizer.peek(2),)
            )
        if self._state == _CHUNK_TRAILERS:
            # trailer 区 EOF 也能忍（历史容错）
            self._complete()
            return self.result
        if self._state == _BODY_LENGTH:
            raise ParseError(
                "truncated body: want %d, got %d"
                % (self._content_length, self._tokenizer.pending_count())
            )
        return self.result

    # ---------- 状态推进 ----------
    def _pump(self):
        dispatch = {
            _REQUEST_LINE: self._do_request_line,
            _HEADERS: self._do_headers,
            _CHUNK_SIZE: self._do_chunk_size,
            _CHUNK_DATA: self._do_chunk_data,
            _CHUNK_TERMINATOR: self._do_chunk_terminator,
            _CHUNK_TRAILERS: self._do_chunk_trailers,
            _BODY_LENGTH: self._do_body_length,
        }
        while self._state in dispatch:
            if dispatch[self._state]():
                # True：当前状态数据不够，停住等下一段
                return

    def _next_line(self, **kwargs):
        """取一行，把 tokenizer 的行长错误翻译成对外 ParseError。"""
        try:
            return self._tokenizer.next_line(**kwargs)
        except LineTooLong as exc:
            raise ParseError("line too long: %d bytes" % exc.length)

    # ---------- 第一段：请求行 ----------
    def _do_request_line(self):
        line = self._next_line()
        if line is None:
            return True
        self._parse_request_line(line)
        self._state = _HEADERS
        return False

    def _parse_request_line(self, line):
        # 手工扫描两个空格把请求行切成三段
        sp1 = line.find(constants.SP)
        if sp1 == -1:
            raise ParseError("malformed request line: %r" % (line,))
        sp2 = line.find(constants.SP, sp1 + 1)
        if sp2 == -1:
            raise ParseError("malformed request line: %r" % (line,))
        if line.find(constants.SP, sp2 + 1) != -1:
            raise ParseError("malformed request line: %r" % (line,))
        method = line[0:sp1]
        target = line[sp1 + 1:sp2]
        version = line[sp2 + 1:len(line)]
        if len(method) == 0 or len(target) == 0:
            raise ParseError("malformed request line: %r" % (line,))
        # method 只收大写字母和连字符（历史校验，M-SEARCH 这类）
        for byte in method:
            if not (constants.METHOD_A <= byte <= constants.METHOD_Z
                    or byte == constants.METHOD_DASH):
                raise ParseError("malformed request line: %r" % (line,))
        # version 必须 HTTP/主.次，主次都是数字
        if version[0:constants.HTTP_PREFIX_LEN] != constants.HTTP_PREFIX:
            raise ParseError("malformed request line: %r" % (line,))
        dot = version.find(constants.DOT)
        if dot == -1:
            raise ParseError("malformed request line: %r" % (line,))
        try:
            int(version[constants.HTTP_PREFIX_LEN:dot])
            int(version[dot + 1:len(version)])
        except ValueError:
            raise ParseError("malformed request line: %r" % (line,))
        self._req.method = method.decode("latin-1")
        self._req.target = target.decode("latin-1")
        self._req.version = version.decode("latin-1")

    # ---------- 第二段：头部 ----------
    def _do_headers(self):
        while True:
            line = self._next_line()
            if line is None:
                return True
            if len(line) == 0:
                # 空行，头块结束，决定 body 怎么读
                self._start_body()
                return False
            self._apply_header_line(line)

    def _apply_header_line(self, raw):
        if raw[0] in constants.FOLD_LEADS:
            # obs-fold：折行续上一条头的值（历史容错）
            if not self._req.headers:
                raise ParseError("malformed header line: %r" % (raw,))
            folded = raw.strip()
            name, old_value = self._req.headers[-1]
            self._req.headers[-1] = (
                name,
                old_value + " " + folded.decode("latin-1"),
            )
            return
        ci = raw.find(b":")
        if ci == -1:
            raise ParseError("malformed header line: %r" % (raw,))
        hname = raw[0:ci]
        hval = raw[ci + 1:len(raw)]
        # 手工去掉值两端的空白（空格 / tab）
        vs = 0
        while vs < len(hval) and hval[vs] in constants.OWS:
            vs = vs + 1
        ve = len(hval)
        while ve > vs and hval[ve - 1] in constants.OWS:
            ve = ve - 1
        hval = hval[vs:ve]
        if len(hname) == 0:
            raise ParseError("malformed header line: %r" % (raw,))
        # 值里不允许控制字符，tab 除外（历史校验）
        for byte in hval:
            if byte < constants.SPACE and byte != constants.TAB:
                raise ParseError("malformed header line: %r" % (raw,))
        self._req.headers.append(
            (hname.decode("latin-1"), hval.decode("latin-1"))
        )

    def _start_body(self):
        # 先扫一遍找 Content-Length，再扫一遍找 Transfer-Encoding（历史两趟）
        content_length = None
        for k, v in self._req.headers:
            if content_length is None and k.lower() == "content-length":
                try:
                    content_length = int(v.strip())
                except ValueError:
                    raise ParseError("invalid content-length: %r" % (v,))
                if content_length < 0:
                    raise ParseError("invalid content-length: %r" % (v,))
        transfer_enc = None
        for k, v in self._req.headers:
            if transfer_enc is None and k.lower() == "transfer-encoding":
                transfer_enc = v

        if transfer_enc is not None:
            if transfer_enc.strip().lower() != "chunked":
                raise ParseError(
                    "unsupported transfer-encoding: %s" % transfer_enc.strip()
                )
            # chunked 优先，Content-Length 忽略（历史行为）
            self._state = _CHUNK_SIZE
            return

        if content_length is not None:
            self._content_length = content_length
            self._state = _BODY_LENGTH
            return

        # 没有 CL 也没有 TE：body 为空，剩余字节忽略（历史容错）
        self._complete()

    # ---------- 第三段：chunked body ----------
    def _do_chunk_size(self):
        # EOF 时统一报 truncated chunk，不做行长判断
        line = self._next_line(enforce_incomplete=False)
        if line is None:
            return True
        semi = line.find(constants.SEMI)
        size_tok = line[0:semi] if semi != -1 else line
        size_tok = size_tok.strip(constants.OWS_BYTES)
        try:
            n = int(size_tok, 16)
        except ValueError:
            raise ParseError("bad chunk size: %r" % (size_tok,))
        if n < 0:
            raise ParseError("bad chunk size: %r" % (size_tok,))
        self._chunk_remaining = n
        if n == 0:
            # 最后一块后面是 trailer 区
            self._state = _CHUNK_TRAILERS
        else:
            self._state = _CHUNK_DATA
        return False

    def _do_chunk_data(self):
        available = self._tokenizer.pending_count()
        if available < self._chunk_remaining:
            # 数据可能在下一段才到，先不报错，由 finish 兜底
            return True
        self._chunk_buf.extend(self._tokenizer.take(self._chunk_remaining))
        self._chunk_remaining = 0
        self._state = _CHUNK_TERMINATOR
        return False

    def _do_chunk_terminator(self):
        head = self._tokenizer.peek(2)
        if not head:
            # chunk 数据刚好到齐，结束符还没到，等下一段
            return True
        first = head[:1]
        if first == b"\n":
            self._tokenizer.skip(1)
            self._state = _CHUNK_SIZE
            return False
        if first == b"\r":
            if head == constants.CRLF:
                self._tokenizer.skip(2)
                self._state = _CHUNK_SIZE
                return False
            if len(head) == 1:
                # 只到了一个 CR，LF 可能在下一段，先等
                return True
        raise ParseError("bad chunk terminator: %r" % (head,))

    def _do_chunk_trailers(self):
        # trailer 收下来但不用，到空行为止；行长不限、EOF 也能忍（历史容错）
        while True:
            line = self._next_line(max_length=None)
            if line is None:
                return True
            if len(line) == 0:
                self._complete()
                return False

    def _complete(self):
        self._req.body = bytes(self._chunk_buf)
        self.result = self._req
        self._state = _DONE

    # ---------- 第三段：Content-Length body ----------
    def _do_body_length(self):
        available = self._tokenizer.pending_count()
        if available < self._content_length:
            return True
        self._req.body = self._tokenizer.take(self._content_length)
        # body 之后的剩余字节忽略（历史容错）
        self.result = self._req
        self._state = _DONE
        return False
