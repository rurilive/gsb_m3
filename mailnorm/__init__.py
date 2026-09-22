"""mailnorm：邮件解析与规范化的小工具包，纯标准库。"""

from .errors import MailParseError
from .headers import Headers, parse_headers, split_addresses, split_header_lines
from .message import Message, split_message
from .mime import decode_transfer, parse_content_type

__all__ = [
    "Headers",
    "MailParseError",
    "Message",
    "decode_transfer",
    "parse_content_type",
    "parse_headers",
    "split_addresses",
    "split_header_lines",
    "split_message",
]
