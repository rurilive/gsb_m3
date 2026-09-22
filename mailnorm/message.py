"""Message：整封邮件文本到头部表加正文。

只处理单段文本邮件：识别 Content-Type 里的主类型与参数，正文原样保留。
multipart 只判断出类型，还没有拆。
"""

from .errors import MailParseError
from .headers import parse_headers
from .mime import decode_transfer, parse_content_type


def split_message(text):
    """按第一个真正的空行把邮件切成头部块与正文。

    返回 (head, body, body_offset)：head 含字段行与行尾换行，body 从空行
    之后开始，body_offset 是 body 在 text 里的下标。没有空行时报错。
    """
    offset = 0
    for chunk in text.splitlines(True):
        offset += len(chunk)
        if chunk.rstrip("\r\n") == "":
            return text[: offset - len(chunk)], text[offset:], offset
    raise MailParseError(
        "message has no blank line between headers and body",
        offset=len(text),
        text=text,
    )


class Message:
    """一封邮件：头部表、原始正文、主类型与参数。

    纯文本邮件直接可用；multipart 只置了 is_multipart 标志，parts 恒为空。
    """

    def __init__(self, headers, body, content_type="text/plain", params=None):
        self.headers = headers
        self.body = body
        self.content_type = content_type
        self.params = dict(params or {})
        self.parts = []
        self.body_offset = 0

    @classmethod
    def parse(cls, text):
        """解析整封邮件文本。"""
        head, body, body_offset = split_message(text)
        headers = parse_headers(head)
        content_type, params = parse_content_type(headers.get("Content-Type", ""))
        msg = cls(headers, body, content_type, params)
        msg.body_offset = body_offset
        return msg

    def get(self, name, default=None):
        return self.headers.get(name, default)

    def __getitem__(self, name):
        return self.headers[name]

    def is_multipart(self):
        return self.content_type.startswith("multipart/")

    def charset(self):
        """charset 参数，缺省按 us-ascii，统一小写。"""
        return (self.params.get("charset") or "us-ascii").strip().lower()

    def text(self):
        """单段文本邮件的正文，返回 str。

        multipart 没有单一正文，报错；非 us-ascii 字符集还没接，也报错。
        """
        if self.is_multipart():
            raise MailParseError("multipart message has no single body")
        payload = decode_transfer(
            self.body, self.headers.get("Content-Transfer-Encoding", "")
        )
        charset = self.charset()
        if charset in ("us-ascii", "ascii"):
            return payload
        raise MailParseError("unsupported charset %r" % charset)

    def __repr__(self):
        return "Message(%r, %d bytes body)" % (self.content_type, len(self.body))
