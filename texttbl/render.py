"""texttbl.render：统一渲染管线。

管线三步，各司其职：
1. model.build_grid / build_columns：数据 -> Cell/Column（宽度、行高是数据）
2. styles.get_style：样式名 -> 边框字符表
3. 本模块的拼装函数：Cell 网格 + 列宽 + 样式 -> 整表文本

输出被 tests/ 逐字节锁着（有几个后台直接 diff 表格输出做告警），
拼装口径一个字都不能变。
"""

from texttbl.model import build_columns, build_grid
from texttbl.styles import get_style
from texttbl.width import text_width


def _row_height(cells):
    """一个行块的高度 = 该行最高 Cell 的行高（至少 1）。"""
    h = 1
    for cell in cells:
        if cell.height > h:
            h = cell.height
    return h


def _render_row(cells, widths, style):
    """把一个行块渲染成若干文本行（左对齐，右侧补空格）。"""
    v = style.vert
    lines = []
    for j in range(_row_height(cells)):
        parts = []
        for cell, w in zip(cells, widths):
            txt = cell.line(j)
            parts.append(" " + txt + " " * (w - text_width(txt)) + " ")
        lines.append(v + v.join(parts) + v)
    return lines


def _markdown_separator(widths):
    """markdown 分隔行：横线数与列宽一致（历史写法，别改）。"""
    sep = "|"
    for w in widths:
        sep = sep + " " + "-" * w + " |"
    return sep


def _assemble(grid, columns, style):
    """Cell 网格 + 列宽 + 样式 -> 文本行列表。"""
    widths = [c.width for c in columns]
    out = []
    if style.top is not None:
        out.append(style.border_line(style.top, widths))
    out.extend(_render_row(grid[0], widths, style))
    if style.markdown:
        out.append(_markdown_separator(widths))
    elif len(grid) > 1:
        out.append(style.border_line(style.mid, widths))
    for row in grid[1:]:
        out.extend(_render_row(row, widths, style))
    if style.bot is not None:
        out.append(style.border_line(style.bot, widths))
    return out


class Table(object):
    """文本表格。用法：Table(["列A", "列B"], style="ascii", wrap=0)。

    add_row 传的格子数可以比列少（缺的当空串），比列多直接报错。
    render() 返回不带尾换行的整表文本。
    """

    def __init__(self, headers, style="ascii", wrap=0):
        self._headers = [str(h) for h in headers]
        self._rows = []
        self._style = style
        self._wrap = wrap

    def add_row(self, *cells):
        if len(cells) > len(self._headers):
            raise ValueError(
                "too many cells: got %d, want %d" % (len(cells), len(self._headers))
            )
        self._rows.append([str(c) for c in cells])
        return self

    def render(self):
        style = get_style(self._style)
        grid = build_grid(self._headers, self._rows, self._wrap)
        columns = build_columns(grid)
        return "\n".join(_assemble(grid, columns, style))
