"""帧协议异常体系。"""


class FrameError(Exception):
    """帧协议错误基类。"""


class HeaderError(FrameError):
    """帧头非法（magic 不匹配、保留位非 0、声明长度超上限）。"""


class CrcError(FrameError):
    """CRC 校验失败，帧内容在传输中被篡改。"""


class UnknownTypeError(FrameError):
    """类型码未注册。"""


class PayloadError(FrameError):
    """载荷不合法（超长、编码失败、解码失败）。"""
