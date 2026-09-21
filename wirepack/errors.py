"""wirepack 的异常层次。

编码侧和解析侧的失败分开，解析侧的异常尽量带上出错位置，
调用方拿着 offset 就能定位到流里的字节。
"""


class WireError(ValueError):
    """本库所有编解码错误的基类。"""


class EncodeError(WireError):
    """调用方给的值不满足线上格式的约束。"""


class DecodeError(WireError):
    """字节流不符合线上格式。

    offset 是出错位置在流中的字节偏移（None 表示位置未知），
    field 是出错字段名，能让调用方直接点到具体字段。
    """

    def __init__(self, message, offset=None, field=None):
        super().__init__(message)
        self.offset = offset
        self.field = field

    def __str__(self):
        text = super().__str__()
        if self.offset is not None:
            text = "%s (offset=%d)" % (text, self.offset)
        if self.field is not None:
            text = "%s [field=%s]" % (text, self.field)
        return text


class FrameDecodeError(DecodeError):
    """0x81 新帧解码失败，解码器 resync 之后继续解后面的内容。

    frame_index 是出错帧在流里的序号（0 起，解失败的帧也占号），
    resync_at 是解码器恢复同步的字节偏移（下一个 0x81 帧头位置；
    流里再没有帧头时指向流末）。
    """

    def __init__(self, message, offset=None, field=None,
                 frame_index=None, resync_at=None):
        super().__init__(message, offset=offset, field=field)
        self.frame_index = frame_index
        self.resync_at = resync_at

    def __str__(self):
        text = super().__str__()
        if self.frame_index is not None:
            text = "%s (frame_index=%d)" % (text, self.frame_index)
        if self.resync_at is not None:
            text = "%s (resync_at=%d)" % (text, self.resync_at)
        return text
