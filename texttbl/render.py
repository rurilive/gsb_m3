"""texttbl.render：Table 对外 API 与统一渲染管线。

管线：原始数据 -> Cell/Column 模型（model.py，宽/高是数据）
     -> 按样式表（styles.py）拼边框和行 -> 整表文本。
输出被 tests/ 逐字节锁着，格式口径一个都不能变。
"""

from texttbl.model import Cell, Column
from texttbl.styles import border_line, get_style, markdown_separator
from texttbl.width import measure


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

    def _build_model(self):
        """原始数据 -> (表头格, 数据行格, 列)。缺失的格子补空 Cell。"""
        cols = len(self._headers)
        header = [Cell(h, self._wrap) for h in self._headers]
        rows = []
        for row in self._rows:
            rows.append(
                [
                    Cell(row[i], self._wrap) if i < len(row) else Cell("", self._wrap)
                    for i in range(cols)
                ]
            )
        columns = [
            Column([header[i]] + [row[i] for row in rows]) for i in range(cols)
        ]
        return header, rows, columns

    def render(self):
        style = get_style(self._style)
        header, rows, columns = self._build_model()
        widths = [col.width for col in columns]

        out_lines = []
        top = border_line(style, widths, "top")
        if top is not None:
            out_lines.append(top)
        out_lines.extend(_render_row(header, widths, style))
        if not style.get("bordered", True):
            out_lines.append(markdown_separator(widths))
        elif len(rows) > 0:
            out_lines.append(border_line(style, widths, "mid"))
        for row in rows:
            out_lines.extend(_render_row(row, widths, style))
        bot = border_line(style, widths, "bot")
        if bot is not None:
            out_lines.append(bot)
        return "\n".join(out_lines)


def _render_row(cells, widths, style):
    """把一行格子（表头或数据行）渲染成若干视觉行，左对齐右侧补空格。"""
    v = style["v"]
    height = max([1] + [cell.height for cell in cells])
    out = []
    for j in range(height):
        parts = []
        for i, cell in enumerate(cells):
            txt = cell.line(j)
            parts.append(" " + txt + " " * (widths[i] - measure(txt)) + " ")
        out.append(v + v.join(parts) + v)
    return out
