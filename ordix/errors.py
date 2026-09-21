"""ordix 的异常类型。"""


class TreeError(Exception):
    """ordix 里所有可预期错误的基类。"""


class InvariantError(TreeError):
    """B+ 树结构自检失败。"""
