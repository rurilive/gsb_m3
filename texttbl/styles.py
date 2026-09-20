"""texttbl.styles：边框样式表。

每套样式是一组字符数据：竖线 v、横线填充 fill、
top/mid/bot 三条边框各自的（左端、连接、右端）。
markdown 不画边框（bordered=False），表头后走自己的分隔行。
新增样式只往 _STYLES 里加一条，不用动渲染逻辑。
"""

_STYLES = {
    "ascii": {
        "v": "|",
        "fill": "-",
        "top": ("+", "+", "+"),
        "mid": ("+", "+", "+"),
        "bot": ("+", "+", "+"),
    },
    "light": {
        "v": "│",
        "fill": "─",
        "top": ("┌", "┬", "┐"),
        "mid": ("├", "┼", "┤"),
        "bot": ("└", "┴", "┘"),
    },
    "heavy": {
        "v": "┃",
        "fill": "━",
        "top": ("┏", "┳", "┓"),
        "mid": ("┣", "╋", "┫"),
        "bot": ("┗", "┻", "┛"),
    },
    "markdown": {
        "v": "|",
        "bordered": False,
    },
}


def get_style(name):
    """按名字取样式表；未知样式在 render 时才报错（历史行为）。"""
    try:
        return _STYLES[name]
    except KeyError:
        raise ValueError("unknown style: %r" % (name,))


def border_line(style, widths, kind):
    """拼一条边框线（kind 为 top/mid/bot）。不画边框的样式返回 None。"""
    if not style.get("bordered", True):
        return None
    left, join, right = style[kind]
    fill = style["fill"]
    return left + join.join(fill * (w + 2) for w in widths) + right


def markdown_separator(widths):
    """markdown 表头下的分隔行：横线数与列宽一致（历史写法）。"""
    sep = "|"
    for w in widths:
        sep = sep + " " + "-" * w + " |"
    return sep
