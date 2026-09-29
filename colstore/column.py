"""一列数据的朴素原样存储。

现有能力：把一列整数按给定顺序原样放好，能整列取回、按下标取单个值、问长度。
编码、惰性解码、按需扫描与谓词下推尚未提供。
"""


class Column:
    """一列整数。

    name 是列名，values 是若干整数，缺省时列名即违规会立刻报错。
    列在构造时校验每个值都是整数，值本身拷进私有列表，之后对外只读。
    """

    def __init__(self, name, values):
        if not isinstance(name, str) or not name:
            raise ValueError("column name must be a non-empty string")
        copied = []
        for v in values:
            if not isinstance(v, int) or isinstance(v, bool):
                raise ValueError("column values must be int")
            copied.append(v)
        self._name = name
        self._values = copied

    @property
    def name(self):
        return self._name

    def __len__(self):
        return len(self._values)

    def get(self, index):
        """按下标取一个值，越界报 IndexError。"""
        return self._values[index]

    def to_list(self):
        """整列原样取回，返回一份新的列表。"""
        return list(self._values)

    def storage_size(self):
        """当前存储占用的元素个数，朴素存储下即元素个数。"""
        return len(self._values)

    def __repr__(self):
        return "Column(name=%s, length=%d)" % (self._name, len(self._values))
