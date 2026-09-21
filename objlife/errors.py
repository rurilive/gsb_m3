"""objlife 的错误类型。"""


class StoreError(Exception):
    """容器相关错误的基类。"""


class UnknownObject(StoreError):
    """对象不存在，或者已经回收。"""


class RefCountError(StoreError):
    """引用计数操作不合法，比如放掉一份自己没有的外部引用。"""


class LinkError(StoreError):
    """连边不合法，比如自指、重复连边，或者摘一条不存在的边。"""
