"""ropepad 的错误类型。"""


class TextError(Exception):
    """文本缓冲相关错误的基类。"""


class RangeError(TextError):
    """位置或者区间越界。"""
