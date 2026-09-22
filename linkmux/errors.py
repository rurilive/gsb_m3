"""linkmux 的异常层次，传输、编解码、会话状态的失败分开。"""


class LinkError(ValueError):
    """本库所有错误的基类。"""


class FrameError(LinkError):
    """帧不符合线上格式，field 指出是哪个字段。"""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field


class LinkClosed(LinkError):
    """连接的某一端已经关了，字节发不出去。"""


class StreamStateError(LinkError):
    """对流的操作不符合当前状态，比如关掉的流上继续写。"""


class StreamReset(LinkError):
    """对端把流重置了，这条流上等着的数据不会再来了。"""

    def __init__(self, message, stream_id=None):
        super().__init__(message)
        self.stream_id = stream_id


class FlowControlError(LinkError):
    """窗口账目对不上，比如发出去的字节超过了对端给的额度。"""
