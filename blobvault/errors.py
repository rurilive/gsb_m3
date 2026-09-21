"""blobvault 的异常类型。"""


class BlobError(Exception):
    """本库所有异常的基类。"""


class InvalidKey(BlobError, ValueError):
    """逻辑名字不合法。"""


class ObjectNotFound(BlobError, KeyError):
    """按名字读对象时没找到。"""

    def __str__(self):
        return "ObjectNotFound: %r" % (self.args[0] if self.args else None,)
