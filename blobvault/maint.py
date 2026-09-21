"""盘上布局的遍历、统计与启动恢复。

ObjectStore 的 list/gc/stats 与启动清扫共用这里的扫描逻辑。
扫描只认真正属于 blobvault 的文件：对象按 64 位摘要命名，引用带
.ref 后缀，临时文件带 .bvtmp 后缀；其余外来文件一律不碰。
"""

import os

from blobvault.keys import (
    GC_DIR,
    INDEX_DIR,
    OBJECTS_DIR,
    REF_SUFFIX,
    TMP_SUFFIX,
    is_digest,
)


def _iter_files(base):
    """遍历目录下的常规文件，产出 (文件名, 绝对路径)；目录不存在则空。"""
    if not os.path.isdir(base):
        return
    for dirpath, _dirnames, filenames in os.walk(base):
        for fn in sorted(filenames):
            yield fn, os.path.join(dirpath, fn)


def iter_objects(root):
    """产出全部内容对象的 (摘要, 绝对路径)，只认 64 位摘要文件名。"""
    for fn, ap in _iter_files(os.path.join(root, OBJECTS_DIR)):
        if is_digest(fn):
            yield fn, ap


def iter_refs(root):
    """产出全部名字引用的 (名字, 绝对路径)，只认 .ref 文件。"""
    for fn, ap in _iter_files(os.path.join(root, INDEX_DIR)):
        if fn.endswith(REF_SUFFIX):
            yield fn[: -len(REF_SUFFIX)], ap


def iter_tmp_files(root):
    """产出 objects/index/gc 三区里所有半成品临时文件的绝对路径。"""
    for area in (OBJECTS_DIR, INDEX_DIR, GC_DIR):
        for _fn, ap in _iter_files(os.path.join(root, area)):
            if os.path.basename(ap).endswith(TMP_SUFFIX):
                yield ap


def disk_usage(root, include_tmp=False):
    """root 下 blobvault 常规文件的字节数总和，目录不存在时为 0。

    默认只算正式的对象、引用和欠账本；include_tmp 时把临时文件也算上。
    """
    total = 0
    paths = [ap for _d, ap in iter_objects(root)]
    paths += [ap for _n, ap in iter_refs(root)]
    ledger = os.path.join(root, GC_DIR, "pending")
    if os.path.isfile(ledger):
        paths.append(ledger)
    if include_tmp:
        paths.extend(iter_tmp_files(root))
    for ap in paths:
        try:
            total += os.path.getsize(ap)
        except OSError:
            pass
    return total
