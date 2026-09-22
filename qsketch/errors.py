"""qsketch 的异常层次。

SketchError 是根；EmptySetError 在空集合上取分位、取均值时抛；
FormatError 在 codec 读入的内容不合规时抛。
"""


class SketchError(Exception):
    """qsketch 所有异常的根。"""


class EmptySetError(SketchError):
    """空集合上取分位、均值、极值。"""


class FormatError(SketchError):
    """落盘内容的格式号或结构不合规。"""
