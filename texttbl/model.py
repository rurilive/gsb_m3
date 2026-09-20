"""texttbl.model：Cell/Column 数据模型。

内容、宽度、行高都是数据；拼装（加边框、补空格）在 render 管线里做。
"""

from texttbl.width import measure


def _wrap_cell(text, wrap):
    """把单元格文本切成若干行。wrap<=0 不换行。

    词间换行（连续空白当一个分隔），超长词硬切。历史口径，别改。
    """
    if wrap is None or wrap <= 0:
        return [text]
    tokens = text.split()
    if len(tokens) == 0:
        return [""]
    lines = []
    cur = ""
    for word in tokens:
        while measure(word) > wrap:
            if cur != "":
                lines.append(cur)
                cur = ""
            lines.append(word[0:wrap])
            word = word[wrap:]
        if cur == "":
            cur = word
        elif measure(cur) + 1 + measure(word) <= wrap:
            cur = cur + " " + word
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


class Cell(object):
    """一个单元格：原始文本 + 换行后的行块，宽/高都是算好的数据。"""

    def __init__(self, text, wrap=0):
        self.text = text
        self.lines = _wrap_cell(text, wrap)
        self.width = max(measure(ln) for ln in self.lines)
        self.height = len(self.lines)

    def line(self, j):
        """第 j 个视觉行；超出本格行数时补空串。"""
        if j < self.height:
            return self.lines[j]
        return ""


class Column(object):
    """一列：表头格 + 若干数据格，列宽 = 全列格子宽度最大。"""

    def __init__(self, cells):
        self.cells = list(cells)
        self.width = 0
        for cell in self.cells:
            if cell.width > self.width:
                self.width = cell.width
