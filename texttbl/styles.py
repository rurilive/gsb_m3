"""texttbl.styles：边框样式表。

每套样式只是一组字符数据，render 不再 if/elif 分叉。加新样式
= 在 STYLES 里加一行，不用动渲染代码。
"""


class BorderStyle(object):
    """一套边框的全部字符。

    top/mid/bot 是 (左端, 交叉, 右端) 三元组，None 表示不画这条横线。
    markdown 为 True 时表头下画 markdown 分隔行（横线数 = 列宽）。
    """

    __slots__ = ("name", "vert", "horiz", "top", "mid", "bot", "markdown")

    def __init__(self, name, vert, horiz, top, mid, bot, markdown=False):
        self.name = name
        self.vert = vert
        self.horiz = horiz
        self.top = top
        self.mid = mid
        self.bot = bot
        self.markdown = markdown

    def border_line(self, triple, widths):
        """拼一条横线：左端 + 各列横线（列宽+2）用交叉符连起来 + 右端。"""
        left, join, right = triple
        segs = [self.horiz * (w + 2) for w in widths]
        return left + join.join(segs) + right


STYLES = {
    "ascii": BorderStyle(
        "ascii",
        vert="|",
        horiz="-",
        top=("+", "+", "+"),
        mid=("+", "+", "+"),
        bot=("+", "+", "+"),
    ),
    "light": BorderStyle(
        "light",
        vert="│",
        horiz="─",
        top=("┌", "┬", "┐"),
        mid=("├", "┼", "┤"),
        bot=("└", "┴", "┘"),
    ),
    "heavy": BorderStyle(
        "heavy",
        vert="┃",
        horiz="━",
        top=("┏", "┳", "┓"),
        mid=("┣", "╋", "┫"),
        bot=("┗", "┻", "┛"),
    ),
    "markdown": BorderStyle(
        "markdown",
        vert="|",
        horiz="-",
        top=None,
        mid=None,
        bot=None,
        markdown=True,
    ),
}


def get_style(name):
    """按名字取样式；未知名字抛 ValueError（历史报错文案，别改）。"""
    try:
        return STYLES[name]
    except KeyError:
        raise ValueError("unknown style: %r" % (name,))
