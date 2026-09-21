"""taglens 的异常类型。"""


class TaglensError(ValueError):
    """输入不对劲时抛的基类，调用方 except TaglensError 能兜住全部。

    后面加解析器、选择器的时候，新异常类型从它派生，
    老的调用方一行都不用改。
    """


class BadTagName(TaglensError):
    """标签名不合法：空串、数字开头、带空格或标点。"""

    def __init__(self, tag):
        self.tag = tag
        super().__init__("标签名不合法：%r" % (tag,))
