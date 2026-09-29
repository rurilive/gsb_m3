"""framefmt 的定长行编码器。

现状是最朴素的一层：一条记录当成若干定宽字段，编码时把每个字段补齐宽度
后拼成一行字符串，解码时再按同样的宽度一行一行切回来。没有长度前缀，没有
字段类型，没有校验和，也没有变长编码。带校验的二进制帧编解码留待补齐。
"""


class LineCodec:
    """把一条记录编码成一行定宽字符串，或从一行切回各字段。

    widths 是每个字段的字符宽度，按顺序给出。encode 接受一组字段值，逐字段
    左对齐补齐到对应宽度后拼接成一行。decode 接受这样一行，按同样的宽度切片，
    再剥掉各字段右侧的填充字符。
    """

    def __init__(self, widths, fill=" "):
        widths = list(widths)
        if not widths:
            raise ValueError("widths 不能为空")
        for width in widths:
            if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
                raise ValueError("每个字段宽度必须是正整数")
        if not isinstance(fill, str) or len(fill) != 1:
            raise ValueError("fill 必须是单个字符")
        self.widths = widths
        self.fill = fill

    def total_width(self):
        return sum(self.widths)

    def encode(self, values):
        values = list(values)
        if len(values) != len(self.widths):
            raise ValueError(
                "字段数量不匹配：期望 %d 个，收到 %d 个"
                % (len(self.widths), len(values))
            )
        parts = []
        for value, width in zip(values, self.widths):
            text = str(value)
            if len(text) > width:
                raise ValueError("字段值超出宽度 %d：%r" % (width, text))
            parts.append(text + self.fill * (width - len(text)))
        return "".join(parts)

    def decode(self, line):
        if not isinstance(line, str):
            raise ValueError("line 必须是字符串")
        expected = self.total_width()
        if len(line) != expected:
            raise ValueError(
                "行长度不匹配：期望 %d，收到 %d" % (expected, len(line))
            )
        out = []
        pos = 0
        for width in self.widths:
            out.append(line[pos:pos + width].rstrip(self.fill))
            pos += width
        return out

    def __repr__(self):
        return "LineCodec(widths=%r)" % (self.widths,)
