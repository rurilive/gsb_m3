"""httpparse.tokenizer：按行切字节的缓冲读取层。

只认字节，不管任何 HTTP 语义。数据可以一次性到，也可以分多段 feed
进来（流式）：内部只维护一个缓冲和一个消费偏移，凑够一行/若干字节
就吐给上层，凑不够就返回 None 等下一段。

行长度上限（含换行符的整行字节数）在这一层强制。历史容错：\\r\\n 和
裸 \\n 都是行结束，吐给上层的行会剥掉行尾 CR。
"""

from httpparse import constants as C


class LineTokenizer(object):
    """字节缓冲上的按行/按字节读取器。

    - feed(data)：追加一段字节。
    - next_line(limit=MAX_LINE_LENGTH)：取出下一行（不含 LF，行尾有 CR
      则剥掉）；还没凑出行返回 None；整行超限时抛 ParseError。
      limit=None 表示不做行长限制（trailer 区历史上不限长）。
    - pending_size()：当前未消费、且还没见到 LF 的字节数（用于头部阶段
      在 EOF 处区分 "line too long" 与 "truncated headers"）。
    - take(n)：原样消费 n 个字节（chunk body）。
    - peek(n)：看前 n 个字节但不消费（chunk 终止符探测）。
    - available()：当前缓冲里未消费的字节总数。
    """

    def __init__(self, data=b""):
        self._buf = bytearray(data)
        self._pos = 0

    def feed(self, data):
        self._buf.extend(data)

    def available(self):
        return len(self._buf) - self._pos

    def pending_size(self):
        if self._pos >= len(self._buf):
            return 0
        if self._buf.find(C.LF, self._pos) == -1:
            return len(self._buf) - self._pos
        return 0

    def next_line(self, limit=C.MAX_LINE_LENGTH):
        if self._pos >= len(self._buf):
            return None
        nl = self._buf.find(C.LF, self._pos)
        if nl == -1:
            return None
        line_len = nl - self._pos
        if limit is not None and line_len > limit:
            self._raise("line too long: %d bytes" % line_len)
        line = bytes(self._buf[self._pos:nl])
        self._pos = nl + 1
        if line and line[-1] == C.CR:
            line = line[:-1]
        return line

    def peek(self, n):
        return bytes(self._buf[self._pos:self._pos + n])

    def take(self, n):
        chunk = bytes(self._buf[self._pos:self._pos + n])
        self._pos += n
        return chunk

    def _raise(self, message):
        # ParseError 定义在 parser（对外门面）；运行时再取，避免循环导入。
        from httpparse.parser import ParseError

        raise ParseError(message)
