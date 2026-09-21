"""blobvault 的异常类型。"""


class BlobError(Exception):
    """本库所有异常的基类。"""


class InvalidKey(BlobError, ValueError):
    """逻辑名字不合法。"""


class ObjectNotFound(BlobError, KeyError):
    """按名字读对象时没找到。"""

    def __str__(self):
        return "ObjectNotFound: %r" % (self.args[0] if self.args else None,)


class CorruptObject(BlobError):
    """盘上对象与索引/摘要对不上：内容被改坏或缺件。"""

    def __str__(self):
        return "CorruptObject: %r" % (self.args[0] if self.args else None,)
