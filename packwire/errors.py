"""packwire 的异常体系。

PackError 是所有编码解码错误的基类；DecodeError 额外带 offset 属性，
指向输入里第一个出问题的字节（约定见 README）。
"""


class PackError(Exception):
    """编解码错误的基类。"""


class EncodeError(PackError):
    """待编码的值不被支持或有字段超界。"""


class DecodeError(PackError):
    """输入字节串解不出来。offset 是第一个出问题的字节下标。"""

    def __init__(self, message, offset):
        super().__init__("%s at offset %d" % (message, offset))
        self.offset = offset
