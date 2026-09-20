"""httpparse.parser：对外门面（三个公开对象的定义与签名都不变）。

实现已拆成三层：
  constants   上限、CRLF、字节字面量
  tokenizer   按行切字节、行长限制、分段 feed（流式接入点）
  message     请求行/头部/body 状态推进与组装
本模块只保留对外 API：ParseError、HttpRequest、parse_request。
"""

from httpparse.message import RequestAssembler


class ParseError(ValueError):
    """请求不合法。错误文本是契约的一部分（下游日志正则匹配），勿改。"""


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


def parse_request(data):
    """解析一个完整的 HTTP/1.1 请求（头部必选，body 按 CL/chunked 跟随）。

    行结束符 \\r\\n 和裸 \\n 都认（历史容错）。头块以第一个空行结束。
    没有 CL 也没有 chunked 时 body 为空，头部之后的剩余字节忽略（历史容错）。
    Transfer-Encoding: chunked 优先于 Content-Length（历史行为）。
    行长度上限按含换行符的整行字节数算，8192（历史口径）。
    """
    if isinstance(data, str):
        raise TypeError("parse_request expects bytes")
    if len(data) == 0:
        raise ParseError("empty request")

    assembler = RequestAssembler()
    assembler.feed(data)
    return assembler.finish()
