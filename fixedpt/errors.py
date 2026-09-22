"""fixedpt 的异常。"""


class FixedPointError(Exception):
    """库内所有错误的基类。"""


class ParseError(FixedPointError):
    """文本解析失败。"""


class DomainOverflow(FixedPointError):
    """定标整数越出账目域的范围。"""
