"""tabox 的最朴素实现：一个只认逗号、只认双引号包裹的定长 CSV 读取器。

现状只有单一写法：按换行断行、按逗号切分、字段两端若成对出现双引号就把它
剥掉。没有方言的概念，分隔符写死是逗号，引号字符写死是双引号，没有转义
规则，没有行终止符配置，不会把引号里的分隔符或换行当作普通字符，没有类型
推断，也没有把结果写回文本的能力。
"""


class CsvReader(object):
    """最朴素的 CSV 读取器：逗号分隔，双引号包裹，整行读入后再切分。"""

    def __init__(self, text):
        self._text = text

    @property
    def text(self):
        """构造时传入的原始文本。"""
        return self._text

    def read(self):
        """把整段文本解析成行列表，每行是字符串字段列表。

        实现方式是最直接的字符串处理：先按换行断成行，再对每行按逗号切分，
        最后把每个字段两端成对的双引号剥掉。空文本返回空列表；文本末尾多出
        的一个换行不会额外产生一个空行。
        """
        lines = self._text.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        rows = []
        for line in lines:
            fields = line.split(",")
            rows.append([self._unquote(field) for field in fields])
        return rows

    @staticmethod
    def _unquote(field):
        """字段两端若成对出现双引号，就把它剥掉，其余原样返回。"""
        if len(field) >= 2 and field.startswith('"') and field.endswith('"'):
            return field[1:-1]
        return field
