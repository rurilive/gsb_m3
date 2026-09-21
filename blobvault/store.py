"""内容寻址的本地对象库。

字节按 sha256 落 objects/<分片>/<摘要>.blob，相同字节全库只存一份；
逻辑名字只是 names.idx 里指向摘要的一条引用。删名字只摘引用，
没有名字指向的对象留到 gc() 才回收，回收失败进 gc-ledger.json 记账重试。

所有落盘走临时文件 + 原子改名；打开 store 时只清扫自家 .bvtmp-*
半成品。读出时按登记摘要重新校验，对象被改坏就抛 ObjectCorrupted，
绝不把错字节交出去。内部一把可重入锁串行化变更。
"""

import os
import threading
from contextlib import contextmanager

from blobvault import content
from blobvault.errors import BlobError, ObjectCorrupted, ObjectNotFound
from blobvault.keys import validate_key


class ObjectStore:
    """名字到字节的内容寻址映射，所有数据放在 root 目录下。"""

    def __init__(self, root):
        self.root = os.fspath(root)
        self._lock = threading.RLock()
        # 只清自家临时半成品，root 尚不存在时无需清扫，也不提前建目录。
        if os.path.isdir(self.root):
            content.sweep_tmp_files(self.root)

    @contextmanager
    def _locked(self):
        """进程内锁 + root 目录 flock，串行化同一库上的并发变更。"""
        with self._lock, content.flock_root(self.root):
            yield

    def put(self, name, data):
        """把 data 写进名字 name，返回对象相对 root 的落盘路径。

        data 只收字节串，传 str 直接 TypeError；同名重复写即覆盖引用。
        相同字节（含别的名字已存过的）在盘上只保留一份。若对象位上
        已有被改坏的同摘要文件，用本次完整字节原子修复。
        """
        if isinstance(data, str) or not isinstance(
            data, (bytes, bytearray, memoryview)
        ):
            raise TypeError("put 只收字节串，收到 %s" % type(data).__name__)
        validate_key(name)
        payload = bytes(data)
        digest = content.digest_of(payload)
        rel = content.object_relpath(digest)
        path = os.path.join(self.root, rel)
        os.makedirs(self.root, exist_ok=True)
        with self._locked():
            if not os.path.exists(path):
                content.atomic_write_bytes(path, payload)
            else:
                try:
                    content.verify_object(path, digest)
                except BlobError:
                    # 位被占且内容对不上：改坏的对象，用正确字节原子覆盖。
                    content.atomic_write_bytes(path, payload)
            names = content.load_names(self.root)
            names[name] = digest
            content.save_names(self.root, names)
        return rel

    def get(self, name):
        """读回 name 的字节。

        名字不存在抛 ObjectNotFound；对象文件被改坏、截断或丢失时
        抛 ObjectCorrupted，不会返回和名字对不上的字节。
        """
        validate_key(name)
        with self._locked():
            names = content.load_names(self.root)
            digest = names.get(name)
            if digest is None:
                raise ObjectNotFound(name)
            path = content.object_path(self.root, digest)
            try:
                return content.read_verified_object(path, digest)
            except BlobError as exc:
                raise ObjectCorrupted(
                    "名字 %r 的对象不可信: %s" % (name, exc)
                ) from None

    def delete(self, name):
        """摘掉名字 name 这条引用，返回是否真的摘到了。

        只动名字索引，不删对象：对象等没有任何名字引用时由 gc() 回收。
        """
        validate_key(name)
        with self._locked():
            names = content.load_names(self.root)
            if name not in names:
                return False
            del names[name]
            content.save_names(self.root, names)
            return True

    def list(self):
        """返回全部名字，升序；空库返回空列表。"""
        with self._locked():
            return sorted(content.load_names(self.root))

    def stats(self):
        """返回盘上现状统计：对象数、名字数、对象占用字节数。

        {"objects": 对象文件数, "names": 名字引用数, "bytes": 对象字节和}。
        只计 objects 下摘要名合法的对象文件，外来文件不算。
        """
        objects = 0
        total_bytes = 0
        with self._locked():
            names = content.load_names(self.root)
            for _digest, _path, size in content.iter_blob_files(self.root):
                objects += 1
                total_bytes += size
        return {"objects": objects, "names": len(names), "bytes": total_bytes}

    def gc(self):
        """回收没有任何名字引用的对象。

        名字删除后对象不会当场消失，只在 gc() 时统一回收。删除失败
        （权限、IO 错误等）的对象记入 gc-ledger.json，之后每次 gc()
        先按当前索引重新确认仍无引用再重试；对象重新被名字指上则
        撤销记账。绝不删除仍被引用的对象，也不让索引指向被删内容。

        返回 {"removed": 删除对象数, "freed_bytes": 释放字节数,
        "failed": 本轮仍失败数, "pending": 账本里待重试总数}。
        """
        with self._locked():
            names = content.load_names(self.root)
            referenced = set(names.values())
            on_disk = {
                digest: (path, size)
                for digest, path, size in content.iter_blob_files(self.root)
            }
            ledger = content.load_ledger(self.root)

            # 本轮新候选 = 盘上无引用、且账本里没记过的对象；
            # 账本条目统一在下面的重试循环处理，避免删两次。
            candidates = {
                digest: item
                for digest, item in on_disk.items()
                if digest not in referenced and digest not in ledger
            }

            removed = 0
            freed = 0
            failed_now = set()

            # 历史失败项优先：先复查引用，仍无引用才重试删除。
            for digest in sorted(ledger):
                if digest in referenced:
                    # 内容重新被名字引用，撤销记账，绝不再删。
                    ledger.pop(digest, None)
                    continue
                item = on_disk.get(digest)
                if item is None:
                    # 对象已经不在盘上（外部清走或先前其实删掉了），销账。
                    ledger.pop(digest, None)
                    continue
                path, size = item
                try:
                    os.remove(path)
                except FileNotFoundError:
                    ledger.pop(digest, None)
                except OSError as exc:
                    entry = ledger[digest]
                    entry["attempts"] = int(entry.get("attempts", 0)) + 1
                    entry["error"] = str(exc) or exc.__class__.__name__
                    failed_now.add(digest)
                else:
                    ledger.pop(digest, None)
                    removed += 1
                    freed += size

            # 本轮新发现的无引用对象。
            for digest in sorted(candidates):
                if digest in ledger or digest in failed_now:
                    continue
                path, size = candidates[digest]
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    ledger[digest] = {
                        "attempts": 1,
                        "error": str(exc) or exc.__class__.__name__,
                    }
                    failed_now.add(digest)
                else:
                    removed += 1
                    freed += size

            content.remove_ledger_if_empty(self.root, ledger)
            return {
                "removed": removed,
                "freed_bytes": freed,
                "failed": len(failed_now),
                "pending": len(ledger),
            }
