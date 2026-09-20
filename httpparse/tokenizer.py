"""httpparse.tokenizer：只管把字节流切成行。

职责（不认识 HTTP 语义）：
- 维护增量缓冲区，数据可以一段段 feed 进来（为流式解析准备）；
- 按 LF 切行，行尾的 CR 一并剥掉（\\r\\n 与裸 \\n 都认，历史容错）；
- 行长上限在这一层强制：长度按含换行符的整行字节数算（剥 LF 之前、
  含 CR），超长抛 LineTooLong，由 message 层翻译成 ParseError。

未取到完整一行时返回 None，已缓冲的残缺行原样保留，等下一次 feed。
缓冲里永远只放“尚未消费”的字节：next_line/take/skip 消费多少就从头
删多少，所以 feed 任何时候调用都只是 append，pump 中途也安全。
"""

from httpparse import constants


class LineTooLong(Exception):
    """行（含 CR、不含 LF）超过上限。message 层负责翻译成 ParseError。"""

    def __init__(self, length):
        super(LineTooLong, self).__init__(length)
        self.length = length


class LineTokenizer(object):
    """增量字节缓冲 + 按行/按字节两种消费方式。"""

    def __init__(self):
        self._buf = bytearray()

    def feed(self, data):
        """追加一段字节。"""
        self._buf.extend(data)

    def next_line(self, max_length=constants.MAX_LINE_LENGTH,
                  enforce_incomplete=True):
        """取下一行（不含行结束符）；没有完整行返回 None。

        max_length：整行（含 CR）字节上限，None 表示不限制（trailer 区）。
        enforce_incomplete：残缺行是否也要按上限判超长。请求行/头部要
               （历史口径），chunk size 行不要（EOF 时统一报 truncated chunk）。
        """
        nl = self._buf.find(constants.LF)
        if nl == -1:
            pending = len(self._buf)
            if (max_length is not None and enforce_incomplete
                    and pending > max_length):
                raise LineTooLong(pending)
            return None
        if max_length is not None and nl > max_length:
            raise LineTooLong(nl)
        line = bytes(self._buf[:nl])
        del self._buf[:nl + 1]
        if line and line[-1] == constants.CR:
            line = line[:-1]
        return line

    def pending_count(self):
        """还没取走的字节数。"""
        return len(self._buf)

    def peek(self, size):
        """看缓冲头部最多 size 字节，不消费（不足时给短切片）。"""
        return bytes(self._buf[:size])

    def take(self, size):
        """取走头部 size 字节（调用方需先用 pending_count 确认够数）。"""
        data = bytes(self._buf[:size])
        del self._buf[:size]
        return data

    def skip(self, size):
        """丢掉头部 size 字节。"""
        del self._buf[:size]
