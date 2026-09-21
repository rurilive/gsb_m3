"""按名字存取二进制对象的本地库。

每个名字对应 objects 分片下的一个文件：put 把字节写到该路径并返回
相对 root 的落盘路径，get 读回，delete 删除，list 扫描目录列出名字。
内部一把锁保护单次操作，root 不存在时首次写入自动创建。
"""

import os
import threading

from blobvault.errors import ObjectNotFound
from blobvault.keys import key_relpath
from blobvault.maint import iter_object_names


class ObjectStore:
    """名字到字节的本地映射，所有数据放在 root 目录下。"""

    def __init__(self, root):
        self.root = os.fspath(root)
        self._lock = threading.Lock()

    def _path(self, name):
        return os.path.join(self.root, key_relpath(name))

    def put(self, name, data):
        """把 data 写进名字 name，返回相对 root 的落盘路径。

        data 只收字节串，传 str 直接 TypeError；同名重复写即覆盖。
        """
        if isinstance(data, str) or not isinstance(
            data, (bytes, bytearray, memoryview)
        ):
            raise TypeError("put 只收字节串，收到 %s" % type(data).__name__)
        path = self._path(name)
        with self._lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(bytes(data))
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    def get(self, name):
        """读回 name 的字节；这个名字不存在时抛 ObjectNotFound。"""
        path = self._path(name)
        with self._lock:
            try:
                with open(path, "rb") as fh:
                    return fh.read()
            except FileNotFoundError:
                raise ObjectNotFound(name) from None
            except IsADirectoryError:
                raise ObjectNotFound(name) from None

    def delete(self, name):
        """删掉名字 name，返回是否真的删到了；名字不存在返回 False。"""
        path = self._path(name)
        with self._lock:
            try:
                os.remove(path)
                return True
            except FileNotFoundError:
                return False
            except IsADirectoryError:
                return False

    def list(self):
        """返回全部名字，升序；空库返回空列表。"""
        return sorted(iter_object_names(self.root))
