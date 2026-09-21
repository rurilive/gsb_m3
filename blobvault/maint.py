"""目录遍历与占用统计。

ObjectStore.list 与 demo 的磁盘统计共用这里的扫描逻辑。
"""

import os

from blobvault.keys import OBJECTS_DIR, OBJECT_SUFFIX


def iter_object_files(root, objects_dir=OBJECTS_DIR, suffix=OBJECT_SUFFIX):
    """遍历 objects 目录，产出 (相对路径, 绝对路径)，相对路径用斜杠分隔。"""
    base = os.path.join(root, objects_dir)
    for dirpath, _dirnames, filenames in os.walk(base):
        for fn in filenames:
            if not fn.endswith(suffix):
                continue
            ap = os.path.join(dirpath, fn)
            yield os.path.relpath(ap, root).replace(os.sep, "/"), ap


def iter_object_names(root, objects_dir=OBJECTS_DIR, suffix=OBJECT_SUFFIX):
    """产出 objects 目录下全部对象名（去掉后缀的文件名）。"""
    for relpath, _ap in iter_object_files(root, objects_dir, suffix):
        _head, fn = relpath.rsplit("/", 1)
        yield fn[: -len(suffix)]


def disk_usage(root):
    """root 下所有常规文件的字节数总和，目录不存在时为 0。"""
    total = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, fn))
            except OSError:
                pass
    return total
