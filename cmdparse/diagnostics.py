"""坐标与诊断：行列口径、失败定位、脱字符渲染。

坐标一律 1 起算、按字符（码点）数，制表符也只占一列。面板把粘进来的
内容当纯文本处理，行列就是直观的屏幕坐标，不做制表符展开，也不按字节
折算。

错误由 ParseError 携带位置，format() 负责渲染成可读的多行文本：第一行
是描述加行列，后面可以缀上出错的那行源码和一行脱字符，指到具体的列。
"""


class ParseError(Exception):
    """解析失败，带出错位置。"""

    def __init__(self, message, line=1, column=1, source_line=None):
        if not isinstance(message, str) or not message:
            raise ValueError("错误描述得是非空字符串")
        if not isinstance(line, int) or not isinstance(column, int):
            raise TypeError("行列都得是 int")
        if line < 1 or column < 1:
            raise ValueError("行列都从 1 起算")
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.source_line = source_line

    def format(self):
        """渲染成多行文本：描述、出错那行、脱字符。"""
        head = "{}（第 {} 行第 {} 列）".format(self.message, self.line, self.column)
        if self.source_line is None:
            return head
        return "\n".join([head, self.source_line,
                          render_caret(self.source_line, self.column)])

    def __str__(self):
        return self.message


def render_caret(source_line, column, width=1):
    """画一行脱字符，指住从 column 起、宽 width 的区间。

    width 留给将来标多字符的区间用，眼下调用方都只指单个字符。
    """
    if column < 1:
        raise ValueError("列从 1 起算")
    if width < 1:
        raise ValueError("脱字符宽度至少 1")
    return " " * (column - 1) + "^" * width
