"""mailnorm 的错误类型。"""


def line_number(text, offset):
    """把字符偏移换算成 1 起的行号；文本为 None 时不换算。"""
    if offset is None or text is None:
        return None
    if offset < 0:
        offset = 0
    elif offset > len(text):
        offset = len(text)
    return text.count("\n", 0, offset) + 1


class MailParseError(ValueError):
    """邮件文本不合规时抛出。

    offset 是出错处相对整份文本的字符下标，line 是对应行号，两个都尽量填，
    调用方拿 e.line / e.offset 就能指到坏在哪儿。
    """

    def __init__(self, reason, offset=None, text=None):
        self.reason = reason
        self.offset = offset
        self.line = line_number(text, offset)
        if offset is None:
            super().__init__(reason)
        else:
            super().__init__("%s (offset %d)" % (reason, offset))

    def located(self, text, base=0):
        """给相对某个子文本的偏移补上基准，换算出行号。"""
        if self.offset is not None:
            self.offset += base
            self.line = line_number(text, self.offset)
        return self
