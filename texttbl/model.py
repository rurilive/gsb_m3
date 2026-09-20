"""texttbl.model：表格的数据模型。

内容、宽度、行高都是数据，渲染前一次性算好；拼装是另一条流水线
（见 render.py），这里不做任何字符串拼接。
"""

from texttbl.width import text_width, wrap_text


class Cell(object):
    """一个单元格：原始内容 + 换行后的行块。行高 = len(lines)。"""

    __slots__ = ("text", "lines")

    def __init__(self, text, wrap=0):
        self.text = text
        self.lines = wrap_text(text, wrap)

    @property
    def height(self):
        return len(self.lines)

    def line(self, j):
        """第 j 个视觉行；超出行高时给空串（矮格子和高格子对齐用）。"""
        if j < len(self.lines):
            return self.lines[j]
        return ""


class Column(object):
    """一列的纵向视图：该列全部 Cell + 列宽（全列最大显示宽）。"""

    def __init__(self, cells):
        self.cells = list(cells)
        self.width = 0
        for cell in self.cells:
            for ln in cell.lines:
                lw = text_width(ln)
                if lw > self.width:
                    self.width = lw


def build_grid(headers, rows, wrap):
    """把表头 + 数据行切成 Cell 网格。grid[0] 是表头行。

    数据行格子数可以比列少，缺的补空 Cell。
    """
    cols = len(headers)
    grid = [[Cell(h, wrap) for h in headers]]
    for row in rows:
        line = []
        for i in range(cols):
            if i < len(row):
                line.append(Cell(row[i], wrap))
            else:
                line.append(Cell("", wrap))
        grid.append(line)
    return grid


def build_columns(grid):
    """按列切网格，算出每列宽度。"""
    if not grid:
        return []
    cols = len(grid[0])
    return [Column([row[i] for row in grid]) for i in range(cols)]
