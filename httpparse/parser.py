"""httpparse.parser：对外门面。

历史上 parse_request 是一个从请求行写到 chunked 的大函数；重构后解析
逻辑拆成三层，这里只保留不可变更的对外 API：

- httpparse.constants：上限、CRLF、字节字面量
- httpparse.tokenizer：按行切字节，行长限制在这一层
- httpparse.message：请求行/头部/body 的状态推进与组装

parse_request 现在只是“把整个请求一次 feed 给状态机再 finish”的薄封装；
要做流式解析时直接用 message.RequestReader 分段 feed 即可。

行结束符 \\r\\n 和裸 \\n 都认（历史容错）。头块以第一个空行结束。
没有 CL 也没有 chunked 时 body 为空，头部之后的剩余字节忽略（历史容错）。
Transfer-Encoding: chunked 优先于 Content-Length（历史行为）。
行长度上限按含换行符的整行字节数算，8192（历史口径）。
"""

from httpparse.message import HttpRequest, ParseError, RequestReader

__all__ = ["HttpRequest", "ParseError", "parse_request", "RequestReader"]


def parse_request(data):
    """解析一个完整的 HTTP/1.1 请求（头部必选，body 按 CL/chunked 跟随）。"""
    if isinstance(data, str):
        raise TypeError("parse_request expects bytes")
    if len(data) == 0:
        raise ParseError("empty request")

    reader = RequestReader()
    reader.feed(data)
    if reader.result is None:
        reader.finish()
    return reader.result
