"""Content-Type 拆解与传输编码解码。

参数按分号硬切、值去掉外层引号，够普通邮件用；引号里再出现分号或转义
引号的写法还没认。
"""

from .errors import MailParseError

_IDENTITY = ("", "7bit", "8bit", "binary")


def parse_content_type(value):
    """'text/plain; charset=utf-8' 拆成 ('text/plain', {'charset': 'utf-8'})。

    空值给默认 text/plain；主类型里没有斜杠时也退回 text/plain；参数名
    统一小写，值剥掉外层成对引号。
    """
    text = (value or "").strip()
    if not text:
        return "text/plain", {}
    pieces = text.split(";")
    media = pieces[0].strip().lower()
    if "/" not in media:
        media = "text/plain"
    params = {}
    for piece in pieces[1:]:
        if piece.strip() == "":
            continue
        name, sep, raw = piece.partition("=")
        name = name.strip().lower()
        if sep == "" or name == "":
            continue
        raw = raw.strip()
        if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
            raw = raw[1:-1]
        params[name] = raw
    return media, params


def decode_transfer(payload, encoding):
    """按 Content-Transfer-Encoding 还原正文。

    现在只认不动内容的几种编码，原样返回字符串；base64 与
    quoted-printable 还没接。
    """
    key = (encoding or "").strip().lower()
    if key in _IDENTITY:
        return payload
    raise MailParseError("unsupported transfer encoding %r" % encoding)
